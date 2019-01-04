from freezegun import freeze_time
import mock
from unittest2 import TestCase
import json

from src import trigger_report
from lib.errors import ValidationError
from lib.validate_constants import VALIDATION_ERROR_MESSAGE
from lib.errors import MissingRequirementsError


class TestTriggerReport(TestCase):
    def setUp(self):
        self.host = '1.1.1.1'
        self.login = 'expensify_user'
        self.password = 'cool_beans'
        self.limit = '100'
        self.bucket_name = 'bucket_name'
        self.template_bucket_key = 'template_bucket_key'
        self.requirements_bucket_key = 'requirements_bucket_key'

        self.os_patch = mock.patch('src.trigger_report.os')
        self.mock_os = self.os_patch.start()
        self.mock_os.environ = {
            'HOST': self.host,
            'LOGIN': self.login,
            'PASSWORD': self.password,
            'LIMIT': self.limit,
            'TEMPLATE_BUCKET_NAME': self.bucket_name,
            'TEMPLATE_BUCKET_KEY': self.template_bucket_key,
            'REQUIREMENTS_BUCKET_KEY': self.requirements_bucket_key,
        }

        self.template = (
            '<#template>\r\n'
            '\t<#some data>\r\n'
            '\t<#some data>\r\n'
            '\t<#some data>\r\n'
            '</#template>\r\n'
        ).encode()

        self.requirements_config = json.dumps(
            {
                'startDate': '2018-06-25',
                'limit': self.limit,
                'reportState': 'APPROVED,REIMBURSED',
                'type': 'combinedReportData',
                'port': 22,
                'fileBasename': 'ideoExpenses',
                'fileExtension': 'csv',
                'reportType': 'combinedReportData',
                'reportLabel': 'Dynamics Export',
                'policyIDList': '1234,5678',
            }
        )

        self.req_config = {
            'inputSettings': {
                'filters': {
                    'startDate': '2018-06-25',
                    'endDate': '2019-06-21',
                    'markedAsExported': 'Dynamics Export',
                    'policyIDList': '1234,5678'
                },
                'limit': self.limit,
                'reportState': 'APPROVED,REIMBURSED',
                'type': 'combinedReportData',
            },
            'onFinish': [
                {
                    'actionName': 'sftpUpload',
                    'sftpData': {
                        'host': self.host,
                        'login': self.login,
                        'password': self.password,
                        'port': 22
                    }
                },
                {
                    'actionName': 'markAsExported',
                    'label': 'Dynamics Export'
                }
            ],
            'onReceive': {'immediateResponse': ['returnRandomFileName']},
            'outputSettings': {'fileBasename': 'ideoExpenses', 'fileExtension': 'csv'},
            'type': 'file'
        }

        self.payload = {
            'request_config': self.req_config,
            'template': self.template
        }
        self.report_name = 'ideoExpenses1234.csv'
        self.expensify_api_patcher = mock.patch(
            'src.trigger_report.api_post'
        )

        self.mock_expensify_api = self.expensify_api_patcher.start()
        self.mock_response = mock.Mock()
        self.mock_response.text = self.report_name
        self.mock_response.status_code = 200
        self.mock_expensify_api.return_value = self.mock_response

        self.mock_fetch_from_s3_patcher = mock.patch('src.trigger_report.fetch_from_s3')
        self.mock_fetch_from_s3 = self.mock_fetch_from_s3_patcher.start()
        self.mock_fetch_from_s3.side_effect = [
            self.template,
            self.requirements_config
        ]

        self.mock_logger_patcher = mock.patch('src.trigger_report.log_error')
        self.mock_logger = self.mock_logger_patcher.start()

        self.mock_log_error_patcher = mock.patch('lib.validate.log_error')
        self.mock_log_error = self.mock_log_error_patcher.start()

    def tearDown(self):
        self.os_patch.stop()
        self.mock_log_error_patcher.stop()

    @freeze_time('2019-06-21')
    def test_api_post_called_with_correct_params(self):
        trigger_report.execute({}, {})

        payload = self.mock_expensify_api.call_args[0][0]

        self.assertEqual(self.payload, payload)

    def test_calls_fetch_from_s3_with_args(self):
        trigger_report.execute({}, {})

        bucket_name, template_bucket_key = self.mock_fetch_from_s3.call_args_list[0][0]

        self.assertEqual(self.bucket_name, bucket_name)
        self.assertEqual(self.template_bucket_key, template_bucket_key)

    def test_calls_fetch_from_s3_with_args_for_requirements(self):
        trigger_report.execute({}, {})

        bucket_name, requirements_bucket_key = self.mock_fetch_from_s3.call_args_list[1][0]

        self.assertEqual(self.bucket_name, bucket_name)
        self.assertEqual(self.requirements_bucket_key, requirements_bucket_key)

    def test_returns_response_text(self):
        response = trigger_report.execute({}, {})

        self.assertEqual(self.report_name, response)

    def test_logs_response_if_failure(self):
        error = 'some error'
        self.mock_response.text = error
        self.mock_response.status_code = 400

        trigger_report.execute({}, {})

        self.mock_logger.assert_called_with(error)

    def test_raises_and_logs_error_for_missing_config_imports(self):
        self.mock_fetch_from_s3.side_effect = [
            self.template,
            '{}'
        ]

        self.assertRaisesRegexp(
            ValidationError,
            VALIDATION_ERROR_MESSAGE,
            trigger_report.execute,
            {},
            'context',
        )
        error_messages = [
            "Requirements Error: expected str for dictionary value @ data['inputSettings']['filters']['startDate']. Got None",
            "Requirements Error: expected a dictionary for dictionary value @ data['inputSettings']['filters']. Got None",
            "Requirements Error: expected str for dictionary value @ data['inputSettings']['limit']. Got None",
            "Requirements Error: not a valid value for dictionary value @ data['inputSettings']['reportState']. Got None",
            "Requirements Error: not a valid value for dictionary value @ data['inputSettings']['type']. Got None",
            "Requirements Error: expected list for dictionary value @ data['onReceive']['immediateResponse']. Got None",
            "Requirements Error: not a valid value for dictionary value @ data['outputSettings']['fileBasename']. Got None",
            "Requirements Error: not a valid value for dictionary value @ data['outputSettings']['fileExtension']. Got None",
            "Requirements Error: expected str for dictionary value @ data['inputSettings']['filters']['policyIDList']. Got None"
        ]

        for error in self.mock_log_error.call_args_list:
            self.assertTrue(error[0][0] in error_messages, error[0][0])

    def test_raises_and_logs_error_for_invalid_date(self):
        requirements_config = json.dumps(
            {
                'startDate': '10/04/2018',
                'limit': self.limit,
                'reportState': 'APPROVED,REIMBURSED',
                'type': 'combinedReportData',
                'port': 22,
                'fileBasename': 'ideoExpenses',
                'fileExtension': 'csv',
                'reportType': 'combinedReportData',
                'policyIDList': '1234,5678',
            }
        )
        self.mock_fetch_from_s3.side_effect = [
            self.template,
            requirements_config
        ]

        self.assertRaisesRegexp(
            ValidationError,
            VALIDATION_ERROR_MESSAGE,
            trigger_report.execute,
            {},
            'context',
        )
        error_messages = [
            "Requirements Error: Date format should be \"YYYY-MM-DD\" for dictionary value @ data['inputSettings']['filters']['startDate']. Got '10/04/2018'",
        ]

        for error in self.mock_log_error.call_args_list:
            self.assertTrue(error[0][0] in error_messages, error[0][0])

    def test_missing_config_file_raises_and_logs_error(self):
        self.mock_fetch_from_s3.side_effect = [
            self.template,
            ''
        ]

        self.assertRaisesRegexp(
            MissingRequirementsError,
            'Missing requirements config file',
            trigger_report.execute,
            {},
            'context',
        )
