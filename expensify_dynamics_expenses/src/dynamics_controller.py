import os
import csv
from dateutil import parser

from lib import sqs_client
from lib.s3_helpers import fetch_from_s3
from lib.dynamics_constants import TIMESTAMP_FORMAT, MESSAGE_DATE_TIME_FIELD, TRANS_DATE_FIELD
from lib.logging_helpers import log_error


def start(event, context):
    csv_string = _fetch_expenses_csv(event)
    if csv_string:
        csv_reader = csv.DictReader(csv_string.splitlines())
        _format_csv_headers(csv_reader)
        payloads = _send_to_d365(csv_reader)

        return payloads

    log_error('Expenses CSV not found', extra_data=event)


def _fetch_expenses_csv(event):
    return fetch_from_s3(
        event['Records'][0]['s3']['bucket']['name'],
        event['Records'][0]['s3']['object']['key']
    ).decode('utf-8')


def _format_csv_headers(csv_reader):
    csv_reader.fieldnames = [
        name if name == 'BatchID' else name.replace('ID', 'Id')
        for name in csv_reader.fieldnames
    ]


def _send_to_d365(csv_reader):
    d365_queue_url = sqs_client.get_queue_url(os.environ.get('QUEUE_NAME'))
    payloads = []
    for row in csv_reader:
        expenses = dict(row)
        _format_expense_payload(expenses)
        sqs_client.send_fifo_message(
            d365_queue_url,
            {
                'endpoint': os.environ['DYNAMICS_EXPENSES_ENDPOINT'],
                'data': expenses
            },
            expenses.get('BatchID')
        )
        payloads.append(expenses)

    return payloads


def _format_expense_payload(expenses):
    amount = expenses.get('Amount')
    if amount:
        expenses['Amount'] = round(float(amount), 2)
    _format_date_for_dynamics(expenses, MESSAGE_DATE_TIME_FIELD)
    _format_date_for_dynamics(expenses, TRANS_DATE_FIELD)


def _format_date_for_dynamics(expenses, expense_key):
    date_to_format = expenses.get(expense_key)
    if date_to_format:
        reformatted_date = parser.parse(date_to_format).strftime(TIMESTAMP_FORMAT)
        expenses[expense_key] = reformatted_date
