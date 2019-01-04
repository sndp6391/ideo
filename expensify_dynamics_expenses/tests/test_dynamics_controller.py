from unittest2 import TestCase
import mock

from src import dynamics_controller
from lib.dynamics_constants import MESSAGE_DATE_TIME_FIELD, TRANS_DATE_FIELD


class TestController(TestCase):
    def setUp(self):
        self.os_patch = mock.patch('src.dynamics_controller.os')
        self.mock_os = self.os_patch.start()

        self.queue_name = 'expenses_queue'
        self.expenses_endpoint = '/data/IDEO_Expenses'
        self.mock_os.environ = {
            'DYNAMICS_EXPENSES_ENDPOINT': self.expenses_endpoint,
            'QUEUE_NAME': self.queue_name
        }

        self.batch_id = '555'
        self.single_row_response = (
            'header1,header2,BatchID\r\n'
            'row1 data1,row1 data2,{}\r\n'.format(self.batch_id)
        ).encode()

        self.multi_row_response = (
            'BatchID,MerchantID,ProjectID,ProjectIDEntity,MessageDateTime,Amount,TransDate\r\n'
            '{},1,11,USA,06/01/2018,200,06/01/2018\r\n'
            '{},2,22,DEU,06/02/2018,300.52,6/2/2018\r\n'
            '{},3,33,GBR,06/03/2018,400.62,06/03/2018\r\n'.format(self.batch_id, self.batch_id, self.batch_id)
        ).encode()

        self.context = {'some_context': 'data about the lambda'}

        self.mock_fetch_from_s3_patcher = mock.patch('src.dynamics_controller.fetch_from_s3')
        self.mock_fetch_from_s3 = self.mock_fetch_from_s3_patcher.start()
        self.mock_fetch_from_s3.return_value = self.single_row_response

        self.mock_logger_patcher = mock.patch('src.dynamics_controller.log_error')
        self.mock_logger = self.mock_logger_patcher.start()

        self.mock_sqs_client_patcher = mock.patch('src.dynamics_controller.sqs_client')
        self.mock_sqs_client = self.mock_sqs_client_patcher.start()
        self.queue_url = 'queue_url'
        self.mock_sqs_client.get_queue_url.return_value = self.queue_url

        self.csv_file = 'file.csv'
        self.bucket_name = 'bucket-name'
        self.event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {
                            "name": self.bucket_name,
                        },
                        "object": {
                            "key": self.csv_file
                        }
                    }
                }
            ]
        }

    def test_calls_s3_bucket(self):
        dynamics_controller.start(self.event, {})

        self.mock_fetch_from_s3.assert_called_with(
            self.bucket_name,
            self.csv_file,
        )

    def test_logs_error_if_no_csv_data(self):
        self.mock_fetch_from_s3.return_value = ('').encode()
        dynamics_controller.start(self.event, {})

        expected_error = self.mock_logger.call_args[0][0]
        expected_extra_data = self.mock_logger.call_args[1]['extra_data']

        self.assertEqual(expected_error, 'Expenses CSV not found')
        self.assertEqual(
            expected_extra_data,
            self.event
        )

    def test_calls_sqs_client_with_single_row(self):
        dynamics_controller.start(self.event, self.context)

        self.mock_sqs_client.send_fifo_message.assert_called_with(
            self.queue_url,
            {
                'endpoint': self.expenses_endpoint,
                'data': {
                    'header1': 'row1 data1',
                    'header2': 'row1 data2',
                    'BatchID': self.batch_id,
                }
            },
            self.batch_id
        )

    def test_calls_dynamics_client_with_multiple_row(self):
        self.mock_fetch_from_s3.return_value = self.multi_row_response
        dynamics_controller.start(self.event, self.context)

        self.mock_sqs_client.send_fifo_message.assert_has_calls(
            [
                mock.call(
                    self.queue_url,
                    {
                        'endpoint': self.expenses_endpoint,
                        'data': {
                            'BatchID': self.batch_id,
                            'MerchantId': '1',
                            'ProjectId': '11',
                            'ProjectIdEntity': 'USA',
                            MESSAGE_DATE_TIME_FIELD: '2018-06-01T00:00:00Z',
                            'Amount': 200.00,
                            TRANS_DATE_FIELD: '2018-06-01T00:00:00Z',
                        }
                    },
                    self.batch_id
                ),
                mock.call(
                    self.queue_url,
                    {
                        'endpoint': self.expenses_endpoint,
                        'data': {
                            'BatchID': self.batch_id,
                            'MerchantId': '2',
                            'ProjectId': '22',
                            'ProjectIdEntity': 'DEU',
                            MESSAGE_DATE_TIME_FIELD: '2018-06-02T00:00:00Z',
                            'Amount': 300.52,
                            TRANS_DATE_FIELD: '2018-06-02T00:00:00Z',
                        }
                    },
                    self.batch_id

                ),
                mock.call(
                    self.queue_url,
                    {
                        'endpoint': self.expenses_endpoint,
                        'data': {
                            'BatchID': self.batch_id,
                            'MerchantId': '3',
                            'ProjectId': '33',
                            'ProjectIdEntity': 'GBR',
                            MESSAGE_DATE_TIME_FIELD: '2018-06-03T00:00:00Z',
                            'Amount': 400.62,
                            TRANS_DATE_FIELD: '2018-06-03T00:00:00Z',
                        }
                    },
                    '555'
                ),
            ]
        )

    def test_returns_d365_payloads(self):
        self.mock_fetch_from_s3.return_value = self.multi_row_response
        return_values = dynamics_controller.start(self.event, {})

        expected_return_values = [
            {
                'BatchID': '555',
                'MerchantId': '1',
                'ProjectId': '11',
                'ProjectIdEntity': 'USA',
                MESSAGE_DATE_TIME_FIELD: '2018-06-01T00:00:00Z',
                'Amount': 200.00,
                TRANS_DATE_FIELD: '2018-06-01T00:00:00Z',
            },
            {
                'BatchID': '555',
                'MerchantId': '2',
                'ProjectId': '22',
                'ProjectIdEntity': 'DEU',
                MESSAGE_DATE_TIME_FIELD: '2018-06-02T00:00:00Z',
                'Amount': 300.52,
                TRANS_DATE_FIELD: '2018-06-02T00:00:00Z',
            },
            {
                'BatchID': '555',
                'MerchantId': '3',
                'ProjectId': '33',
                'ProjectIdEntity': 'GBR',
                MESSAGE_DATE_TIME_FIELD: '2018-06-03T00:00:00Z',
                'Amount': 400.62,
                TRANS_DATE_FIELD: '2018-06-03T00:00:00Z',
            }
        ]

        self.assertEqual(return_values, expected_return_values)
