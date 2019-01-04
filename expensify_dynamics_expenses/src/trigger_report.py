import os
from datetime import datetime
import json

from lib.expensify_client import api_post
from lib.s3_helpers import fetch_from_s3
from lib.logging_helpers import log_error
from lib.validate import validate_schema
from lib.errors import MissingRequirementsError
from src.schema import sftp_schema, requirements_schema

START_DATE = '2018-05-01'


def execute(event, context):
    template = fetch_from_s3(
        os.environ['TEMPLATE_BUCKET_NAME'],
        os.environ['TEMPLATE_BUCKET_KEY']
    )

    response = api_post(
        {
            'request_config': _get_request_config(),
            'template': template
        },
        {}
    )

    if response.status_code != 200:
        log_error(response.text)

    return response.text


def _get_request_config():
    today = datetime.now().strftime('%Y-%m-%d')
    req_config = _fetch_req_config()
    request_config = {
        'inputSettings': {
            'filters': {
                'startDate': req_config.get('startDate'),
                'endDate': today,
                'markedAsExported': req_config.get('reportLabel'),
                'policyIDList': req_config.get('policyIDList')
            },
            'limit': req_config.get('limit'),
            'reportState': req_config.get('reportState'),
            'type': req_config.get('reportType')
        },
        'onFinish': [
            _get_sftp_config(),
            {
                'actionName': 'markAsExported',
                'label': req_config.get('reportLabel')
            },
        ],
        'onReceive': {'immediateResponse': ['returnRandomFileName']},
        'outputSettings': {
            'fileBasename': req_config.get('fileBasename'),
            'fileExtension': req_config.get('fileExtension')
        },
        'type': 'file'
    }

    validate_schema(
        requirements_schema,
        request_config,
        'Requirements Error'
    )

    return request_config


def _get_sftp_config():
    sftp_config = {
        'actionName': 'sftpUpload',
        'sftpData': {
            'host': os.environ.get('HOST'),
            'login': os.environ.get('LOGIN'),
            'password': os.environ.get('PASSWORD'),
            'port': 22
        }
    }

    validate_schema(
        sftp_schema,
        sftp_config,
        'Requirements Error'
    )
    return sftp_config


def _fetch_req_config():
    raw_req_config = fetch_from_s3(
        os.environ['TEMPLATE_BUCKET_NAME'],
        os.environ['REQUIREMENTS_BUCKET_KEY']
    )

    try:
        return json.loads(raw_req_config)
    except json.JSONDecodeError:
        raise MissingRequirementsError('Missing requirements config file')
