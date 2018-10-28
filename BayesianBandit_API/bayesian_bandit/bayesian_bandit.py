__author__ = 'Ksenia'


from eve import Eve
from eve.auth import requires_auth, BasicAuth
from flask import Response, json, request, make_response, jsonify
import pandas as pd
import numpy as np
from scipy import stats
from cerberus import Validator
import random

def merge_two_dicts(x, y):
    """Given two dicts, merge them into a new dict as a shallow copy."""
    z = x.copy()
    z.update(y)
    return z


EPSILON = 0.2
CI_WIDTH_H0 = 0.02  # width of the allowable range for real value of performance estimates
CONF_LEVEL = 0.95  # confidence level

# Validate input json
INPUT_SCHEMA = {
    # 'datetime': {
    #     'type': 'datetime',
    #     'required': True,
    # },
    'experiment_id': {
        'type': 'string',
        'required': True
    },
    'campaign_id': {
        'type': 'string',
        'required': True
    },
    'batch_id': {
        'type': 'integer',
        'required': True
    },
    'time_delay': {  # number of seconds between emails were sent and stats collection moment
        'type': 'integer',
        'required': True,
        'min': 0
    },
    'subjects_stats': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'subject_id': {
                    'type': 'string',
                    'required': True
                },
                'emails_sent': {
                    'type': 'integer',
                    'min': 0,
                    'required': True
                },
                'emails_opened': {
                    'type': 'integer',
                    'min': 0,
                    'required': True
                }
            }
        },
        'required': True,
        'empty': False
    }
}
validator = Validator(INPUT_SCHEMA)


class MyBasicAuth(BasicAuth):
    def check_auth(self, username, password, allowed_roles, resource, method):
        if str(resource) in ('bayesian_bandit'):
            # 'bayesian_bandit' is public
            return True
        else:
            # all the other resources are secured
            return username == 'admin' and password == 'qHQByAswXuEADz4'
AUTH_HEADER = {"Authorization": "Basic YWRtaW46cUhRQnlBc3dYdUVBRHo0"}

app = Eve(auth=MyBasicAuth)
client = app.test_client()

@app.route('/bayesian_bandit', methods=['POST'])
def api_bayesian_bandit():
    args = request.get_json(force=True)
    if not validator.validate(args):
        js = json.dumps(validator.errors, indent=4)

        return Response('ERROR: Invalid json\n %s\n' % js, status=422, mimetype='application/json')
    else:
        # TODO: fix issue with datetime format
        input_base_keys = [  # 'datetime',
            'experiment_id',
            'campaign_id',
            'batch_id',
            'time_delay']

        experiment_id = args.get('experiment_id')
        campaign_id = args.get('campaign_id')
        batch_id = args.get('batch_id')
        subject_id_list = [el.get('subject_id') for el in args.get('subjects_stats')]
        n_subjects = len(subject_id_list)

        input_coll = app.data.driver.db['input']
        black_box_coll = app.data.driver.db['black_box']

        _search_params = {
            "experiment_id": experiment_id,
            "campaign_id": campaign_id,
            "batch_id": batch_id
        }

        # Check uniqueness of input
        input_coll_pointer = input_coll.find(_search_params)
        if len(list(input_coll_pointer)) > 0:
            js = 'ERROR: Input data already exists for config:\n %s\n' % json.dumps(_search_params, indent=4)

            return Response(js, status=422, mimetype='application/json')
        else:
            # Check whether there is a record for the previous batch for current campaign_id+experiment_id:
            _search_params['batch_id'] = batch_id - 1
            if batch_id > 0:
                # ttt = list(black_box_coll.find(_search_params))
                if len(list(black_box_coll.find(_search_params)))==0:
                    js = 'ERROR: Missing data for the previous batch:\n %s\n' % json.dumps(_search_params, indent=4)

                    return Response(js, status=422, mimetype='application/json')

            # Write new records into INPUT collection:
            input_base = {k: args[k] for k in input_base_keys}
            input = [merge_two_dicts(input_base, _sub_stats) for _sub_stats in args.get('subjects_stats')]

            resp_tmp = client.post('/input', data=json.dumps(input), content_type='application/json', headers=AUTH_HEADER)
            print '... NEW record to the "input" collection has been added ...'

            # get dataframe with current batch subjects performance
            subjects_stats = pd.DataFrame(args.get('subjects_stats'))
            # subjects_stats['open_rate'] = subjects_stats['emails_opened'] / subjects_stats['emails_sent']

            # Update beta distribution parameters:
            proportions = {_subj_id: 1. / n_subjects for _subj_id in subject_id_list}
            alpha = {_subj_id: 1. for _subj_id in subject_id_list}
            beta = {_subj_id: 1. for _subj_id in subject_id_list}
            beta_params = pd.DataFrame({
                "experiment_id": experiment_id,
                "campaign_id": campaign_id,
                "batch_id": batch_id,
                "subject_id": subject_id_list,
                "alpha": 1.,
                "beta": 1.
            })
            if batch_id > 0:
                black_box_pointer = black_box_coll.find(_search_params)
                beta_params = (pd.DataFrame(list(black_box_pointer))[
                                   ["experiment_id", "campaign_id", "batch_id", "subject_id", "alpha", "beta"]]
                               .drop_duplicates()
                               )

                beta_params = beta_params.merge(subjects_stats,
                                                on='subject_id',
                                                how='outer')
                # fill NAs (if there are some):
                if set(subject_id_list) != set(beta_params['subject_id']):
                    mask = merge_two_dicts(_search_params,
                                           {"alpha": 1.,
                                            "beta": 1.,
                                            "emails_sent": 0,
                                            "emails_opened": 0})
                    beta_params = beta_params.fillna(mask)
                    # update subject_id_list
                    subject_id_list = beta_params['subject_id'].tolist()

                # update params:
                beta_params['batch_id'] = batch_id
                beta_params['alpha'] += beta_params['emails_opened']
                beta_params['beta'] += beta_params['emails_sent'] - beta_params['emails_opened']

                # Generate proportions according to current stats:
                alpha = {_subj_id: _alpha for _subj_id, _alpha in
                         zip(beta_params['subject_id'], beta_params['alpha'])}
                beta = {_subj_id: _beta for _subj_id, _beta in zip(beta_params['subject_id'], beta_params['beta'])}

		# Calculate narrowed X2 CI for current estimates:
                _sign_lev_tmp = (1 - CONF_LEVEL) / 2
                CI_narrowedX2 = pd.DataFrame([{'subject_id': _subj_id,
                                    'open_rate': alpha[_subj_id]/(alpha[_subj_id]+beta[_subj_id]),
                                    'CI_lower': stats.beta(alpha[_subj_id]*2, beta[_subj_id]*2).ppf(_sign_lev_tmp),
                                    'CI_upper': stats.beta(alpha[_subj_id]*2, beta[_subj_id]*2).ppf(1 - _sign_lev_tmp)} for
                                   _subj_id
                                   in subject_id_list])

                # get subset of potential best subjects:
                # 1. get best estimate:
                subj_best_est = CI_narrowedX2.iloc[CI_narrowedX2['open_rate'].idxmax()]
                # print 'best subject so far: %s' % str(subj_best_est)
                # 2. get all subj  with overlapping CI:
                subj_best_ids_list = CI_narrowedX2.loc[CI_narrowedX2['CI_upper']>=subj_best_est['CI_lower'], 'subject_id'].tolist()
                # print 'best subjectS candidates: %s' % str(subj_best_ids_list)

                # generate random beta values for POTENTIALLY BEST estimates:
                theta = {_subj_id: np.random.beta(alpha[_subj_id]*2, beta[_subj_id]*2) for _subj_id in subj_best_ids_list}   # <--- optimized Bayes
                # theta = {_subj_id: np.random.beta(alpha[_subj_id]*2, beta[_subj_id]*2) for _subj_id in subject_id_list}   # <--- simple bayes
                subj_best, theta_best = sorted(theta.items(), key=lambda t: t[1], reverse=True)[0]

		# Proportional proportions for nonwin subj
                theta_nonwin = {k:v for k,v in theta.iteritems() if k!=subj_best}
                nonwin_sum_tmp = sum(theta_nonwin.values())
                proportions = {k:v/nonwin_sum_tmp*EPSILON for k,v in theta_nonwin.iteritems()}
                proportions.update({subj_best:(1-EPSILON)})
		# update with NULLs for worst subjects:
                proportions.update({_subj_id:0 for _subj_id in [s for s in subject_id_list if s not in subj_best_ids_list]})

            # Round proportions:
            proportions = {k:round(v,2) for k,v in proportions.iteritems()}
            prop_diff_1 = round(1 - sum(proportions.values()),2)
            subj_upd_candidates = [k for k,v in proportions.iteritems() if v > -prop_diff_1]
            proportions[random.choice(subj_upd_candidates)] += prop_diff_1   # <--- change proportions.keys() to subj_best_ids_list
            proportions = {k: round(v, 2) for k, v in proportions.iteritems()}
            #proportions[random.choice(proportions.keys())] += prop_diff_1

            # Write updated beta params into black_box collection:
            beta_params = beta_params[["experiment_id", "campaign_id", "batch_id", "subject_id", "alpha", "beta"]]
            black_box_input = [beta_params.iloc[i].to_dict() for i in beta_params.index]
            client.post('/black_box', data=json.dumps(black_box_input), content_type='application/json', headers=AUTH_HEADER)
            print '... NEW record to the "black_box" collection has been added ...'

            # Write output proportions+CI info into output collection:
            # Calculate CI for current estimates:
            _sign_lev_tmp = (1 - CONF_LEVEL) / 2
            CI = pd.DataFrame([{'subject_id': _subj_id,
                                'CI_lower': stats.beta(alpha[_subj_id], beta[_subj_id]).ppf(_sign_lev_tmp),
                                'CI_upper': stats.beta(alpha[_subj_id], beta[_subj_id]).ppf(1 - _sign_lev_tmp)} for
                               _subj_id
                               in subject_id_list])
            CI['CI_width'] = CI['CI_upper'] - CI['CI_lower']
            CI['is_significant'] = (CI['CI_width'] <= CI_WIDTH_H0).astype(int)

            output = (pd.DataFrame([proportions], index=['proportion']).T
                      .merge(CI, right_on='subject_id', left_index=True)
                      )
            output = (beta_params[["experiment_id", "campaign_id", "batch_id", "subject_id"]]
                      .merge(output, on='subject_id')
                      )
            output['batch_id'] = batch_id + 1
            output = output.merge(CI)

            out = [output.iloc[i].to_dict() for i in output.index]
            client.post('/output', data=json.dumps(out), content_type='application/json', headers=AUTH_HEADER)
            print '... NEW record to the "output" collection has been added ...'

            # return updated proportions for the next batch:
            tmp = {
                "experiment_id": experiment_id,
                "campaign_id": campaign_id,
                "batch_id": batch_id + 1
            }

            # add CI info to the final output:
            output = output[["subject_id", "proportion", "CI_upper", "CI_lower", "CI_width", "is_significant"]]
            js = json.dumps(merge_two_dicts(tmp, {"config": [output.iloc[i].to_dict() for i in output.index]})
                            ,indent=4     # uncomment to make pretty printing of output json string
                            )

            ## output only recalculated proportions:
            #js = json.dumps(merge_two_dicts(tmp, {"proportions": proportions})
            #                ,indent=4     # uncomment to make pretty printing of output json string
            #                )
            
            return Response(js + '\n', status=200, mimetype='application/json')


if __name__ == '__main__':
    app.run(debug=True)



