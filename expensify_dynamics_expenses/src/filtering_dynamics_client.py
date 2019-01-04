from lib.dynamics_client import api_post as lib_api_post
from lib.expensify_constants import EXPENSE_UNIQUE_ID


def api_post(event, context):
    if EXPENSE_UNIQUE_ID in event['data']:
        del event['data'][EXPENSE_UNIQUE_ID]

    return lib_api_post(event, context)
