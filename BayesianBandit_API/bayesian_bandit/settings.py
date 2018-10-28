__author__ = 'Ksenia'

RENDERERS = [
    'eve.render.JSONRenderer',
    'eve.render.XMLRenderer'
]

SERVER_NAME = None

# Change default datetime format:
#   - default: '%a, %d %b %Y %H:%M:%S GMT'   e.g.:  "Tue, 02 Apr 2013 10:29:13 GMT”
#   - update to: '%d/%m/%Y %H:%M:%S.%f'   e.g.:  ""
DATE_FORMAT = '%d/%m/%Y %H:%M:%S GMT'

# MongoDB config
MONGO_URI = "mongodb://ksenia:6kTWWzfs62@127.0.0.1:27017/bandit_dbs"


# Enable reads (GET), inserts (POST) and DELETE for resources/collections
# (if you omit this line, the API will default to ['GET'] and provide
# read-only access to the endpoint).
RESOURCE_METHODS = ['GET', 'POST', 'DELETE']
# Enable reads (GET), edits (PATCH), replacements (PUT) and deletes of
# individual items  (defaults to read-only item access).
ITEM_METHODS = ['GET', 'PATCH', 'PUT', 'DELETE']

DOMAIN = {
    'input': {
        'schema': {
            # 'datetime': {
            #     'type': 'datetime',
            #     'required': True,
            # },
            'experiment_id': {
                'type': 'string',
                'required': True,
            },
            'campaign_id': {
                'type': 'string',
                'required': True,
            },
            'batch_id': {
                'type': 'integer',
                'min': 0,
                'required': True,
            },
            'time_delay': {  # number of seconds between emails were sent and stats collection moment
                'type': 'float',
                'min': 0,
                'required': True,
                'default': 0,
            },
            'subject_id': {
                'type': 'string',
                'required': True,
            },
            'emails_sent': {
                'type': 'integer',
                'min': 0,
                'required': True,
                'default': 0,
            },
            'emails_opened': {
                'type': 'integer',
                'min': 0,
                'required': True,
                'default': 0,
            }
        }
    },

    'black_box': {
        'schema': {
            'experiment_id': {
                'type': 'string',
                'required': True,
            },
            'campaign_id': {
                'type': 'string',
                'required': True,
            },
            'batch_id': {
                'type': 'integer',
                'min': 0,
                'required': True,
            },
            'subject_id': {
                'type': 'string',
                'required': True,
            },

            # Beta distribution parameters
            'alpha': {
                'type': 'float',
                'min': 1.,
                'required': True,
                'default': 1.,
            },
            'beta': {
                'type': 'float',
                'min': 1.,
                'required': True,
                'default': 1.,
            }
        }
    },

    'output': {
        'schema': {
            'experiment_id': {
                'type': 'string',
                'required': True,
            },
            'campaign_id': {
                'type': 'string',
                'required': True,
            },
            'batch_id': {
                'type': 'integer',
                'min': 0,
                'required': True,
            },
            'subject_id': {
                'type': 'string',
                'required': True,
            },
            'proportion': {
                'type': 'float',
                'required': True
            },
            'CI_lower': {
                'type': 'float',
                'required': True
            },
            'CI_upper': {
                'type': 'float',
                'required': True
            },
            'CI_width': {
                'type': 'float',
                'required': True
            },
            'is_significant': {
                'type': 'integer',
                'required': True,
                'allowed': [0,1]
            }

        }
    }
}



