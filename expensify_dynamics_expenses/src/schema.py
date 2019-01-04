from voluptuous import Schema, Required, ALLOW_EXTRA, All, Invalid
from lib.validator import truthy
from datetime import datetime


def Date(v):
    try:
        return datetime.strptime(v, '%Y-%m-%d')
    except ValueError:
        raise Invalid('Date format should be "YYYY-MM-DD"')


sftp_schema = Schema(
    {
        Required('actionName'): 'sftpUpload',
        Required('sftpData'): {
            Required('host'): All(str, truthy),
            Required('login'): All(str, truthy),
            Required('password'): All(str, truthy),
            Required('port'): 22,
        },
    }
)


requirements_schema = Schema(
    {
        Required('inputSettings'): {
            Required('filters'): {
                Required('startDate'): All(str, Date),
                Required('endDate'): All(str, truthy, Date),
                Required('policyIDList'): All(str, truthy),
            },
            Required('limit'): All(str, truthy),
            Required('reportState'): 'APPROVED,REIMBURSED',
            Required('type'): 'combinedReportData',
        },
        Required('type'): 'file',
        Required('onReceive'): {
            Required('immediateResponse'): All(
                list,
                truthy
            )
        },
        Required('outputSettings'): {
            Required('fileBasename'): 'ideoExpenses',
            Required('fileExtension'): 'csv',
        },
        Required('onFinish'): All(truthy, list),
    },
    extra=ALLOW_EXTRA,
)
