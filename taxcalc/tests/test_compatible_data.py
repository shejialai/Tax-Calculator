
"""
Tests of the compatible_data fields in the current_law_policy.json file.

In order to tap into the parallelization capabilities of py.test, this module
leans heavily on py.tests's `parametrization` method. Once you do so, the
plug-in pytest-xdist is able to run all parametrized functions in parallel
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 test_compatible_data.py
# pylint --disable=locally-disabled test_compatible_data.py

from __future__ import print_function
import copy
import pytest
import numpy as np
import six
from taxcalc import Policy, Records, Calculator  # pylint: disable=import-error


@pytest.fixture(scope='module', name='allparams')
def fixture_allparams():
    """
    Return metadata for current law parameters
    """
    return Policy.default_data(metadata=True)


def test_compatible_data_presence(allparams):
    """
    Test that every parameter in the current_law_policy.json file
    has a compatible_data field that is a dictionary.
    """
    compatible_data_keys_set = set(['puf', 'cps'])

    # Nested function used only in test_compatible_data_presence
    def valid_compatible_data(compatible_data):
        """
        Return True if compatible_data is a valid dictionary;
        otherwise return False
        """
        if not isinstance(compatible_data, dict):
            return False
        if set(compatible_data.keys()) != compatible_data_keys_set:
            return False
        for key in compatible_data:
            boolean = (compatible_data[key] is True or
                       compatible_data[key] is False)
            if not boolean:
                return False
        return True

    # Main logic of test_compatible_data_presence function
    problem_pnames = list()
    for pname in allparams:
        if 'compatible_data' in allparams[pname]:
            compatible_data = allparams[pname]['compatible_data']
        else:
            compatible_data = None
        if not valid_compatible_data(compatible_data):
            problem_pnames.append(pname)
    if problem_pnames:
        msg = '{} has no or invalid compatible_data field'
        for pname in problem_pnames:
            print(msg.format(pname))
        assert 'list of problem_pnames' == 'empty list'

XX_YEAR = 2019
TEST_YEAR = 2020


@pytest.fixture(scope='module', name='reform_xx')
def fixture_reform_xx():
    """
    Fixture for reform dictionary where reform starts before TEST_YEAR.

    The provisions in the baseline reform, designated in _reform_xx,
    is designed to activate parameters that are inactive under current law.
    For example a phaseout rate for a new credit is inactive is the credit's
    amount is set to zero under current law. In order to activate the phaseout
    rate, the credit amount should be set above zero. The provisions interact
    with each other: you may acidentally deactivate one parameter
    by introducing a provision to activate another. If you find that a pair of
    parameters are impossible test jointly, add one to the local variable
    `exempt_from_testing` in `test_compatible_data()` as a last resort.
    """
    assert XX_YEAR < TEST_YEAR

    # Set baseline to activate parameters that are inactive under current law.
    _reform_xx = {
        XX_YEAR: {
            '_FST_AGI_trt': [0.5],
            '_CTC_new_rt': [0.5],
            '_CTC_new_c': [5000],
            '_CTC_new_prt': [0.1],
            '_CTC_new_refund_limited': [True],
            '_CTC_new_refund_limit_payroll_rt': [1],
            '_ID_BenefitSurtax_trt': [0.1],
            '_ID_BenefitSurtax_crt': [0.1],
            '_UBI_u18': [1000],
            '_UBI_1820': [1000],
            '_UBI_21': [1000],
            '_PT_brk7': [[1000000, 1000000, 1000000, 1000000, 1000000]],
            '_II_credit_prt': [0.1],
            '_II_credit': [[100, 100, 100, 100, 100]],
            '_CG_brk3': [[1000000, 1000000, 1000000, 1000000, 1000000]],
            '_ALD_Dependents_Child_c': [1000],
            '_II_credit_nr': [[1000, 1000, 1000, 1000, 1000]],
            '_II_credit_nr_prt': [0.1],
            '_AMT_CG_brk3': [[500000, 500000, 500000, 500000, 500000]],
            '_AGI_surtax_thd': [[1000000, 1000000, 1000000, 1000000, 1000000]],
            '_AGI_surtax_trt': [0.5],
            '_ID_AmountCap_rt': [0.9],
            '_II_brk7': [[1000000, 1000000, 1000000, 1000000, 1000000]],
            '_ID_BenefitCap_rt': [0.4],
            '_PT_rt7': [.35],
            '_II_em': [1000],
            '_ID_Casualty_hc': [.1],
            '_ID_Miscellaneous_hc': [.1],
            '_ID_prt': [0.03],
            '_ID_crt': [0.8]
        }
    }
    return _reform_xx


@pytest.fixture(scope='module', name='sorted_param_names')
def fixture_sorted_param_names(allparams):
    """
    Fixture for storing a sorted parameter list
    """
    return sorted(list(allparams.keys()))

NPARAMS = len(Policy.default_data())
BATCHSIZE = 10
BATCHES = int(np.floor(NPARAMS / BATCHSIZE)) + 1


@pytest.fixture(scope='module', name='allparams_batch',
                params=[i for i in range(0, BATCHES)])
def fixture_allparams_batch(request, allparams, sorted_param_names):
    """
    Fixture for grouping Tax-Calculator parameters

    Experiments indicated that there is some overhead when you run
    `test_compatible_data` on each parameter individually. Suppose it takes X
    amount of time to set up the test data for `test_compatible_data` and Y
    amount of time to run `test_compatible_data` on each parameter wihtout
    parallelization. Then, if there is no overhead from parallelization, you
    would expect it to take Y + (X / NUMBER_WORKERS) to run these tests in
    parallel. Note that setup data is only created once if you set the
    fixture scope to 'module'. However, experiments indicated that there was
    so much overhead that the tests weren't that much faster in parallel than
    if they were run sequentially.

    I found that running the parameters in batches decreased the amount of
    overhead. Further, there was an optimal batch size that I found through
    trial and error. On my local machine, this was something like 10
    parameters. Others may find a different optimal batch size on their
    machines. Further, if the number of parameters changes, the optimal
    batch size could change, too.

    Math for partitioning the parameters:

    Suppose we have N parameters and choose batch size n. Then, we have
    B batches where B equals floor(N / n) + 1.

    Case 1: N  %  n = 0
    Then we have:
    idx_min = {i * b, i = 0, 1, 2, 3, ..., B - 1} and
    idx_max = {min((i + 1) * b, N), i = 0, 1, 2, 3, ..., B - 1}

    So, if i equals 0, the batch contains the first b - 1 parameters.
    Then, if i equals B, then idx_min is n * (B - 1) = N and idx_max is N and
    thus, the last batch is empty.

    Case 2: N  %  n = r > 0
    Then, everything is the same as case 1, except for the final batch.
    In the final batch, idx_min = b * (B - 1) = b * floor(N / n) < N, and
    idx_max is N. So, we our final batch size is
    idx_max - idx_min = N - b * B = r.

    returns: dictionary of size, BATCHSIZE, or for the final batch,
    either an empty dictionary or dictionary of size NPARAMS mod BATCHSIZE
    """
    idx = request.param
    idx_start = idx * BATCHSIZE
    idx_end = min((idx + 1) * BATCHSIZE, NPARAMS)
    pnames = sorted_param_names[idx_start: idx_end]
    return {pname: allparams[pname] for pname in pnames}


@pytest.fixture(scope='module', name='tc_objs',
                params=[True, False])
def fixture_tc_objs(request, reform_xx, puf_subsample, cps_subsample):
    """
    Fixture for creating Tax-Calculator objects that use the PUF and
    use the CPS (called only twice: once for PUF and once for CPS)
    """
    puftest = request.param
    p_xx = Policy()
    p_xx.implement_reform(reform_xx)
    if puftest:
        rec_xx = Records(data=puf_subsample)
    else:
        rec_xx = Records.cps_constructor(data=cps_subsample)
    c_xx = Calculator(policy=p_xx, records=rec_xx, verbose=False)
    c_xx.advance_to_year(TEST_YEAR)
    c_xx.calc_all()
    return rec_xx, c_xx, puftest


@pytest.mark.pre_release
@pytest.mark.compatible_data
@pytest.mark.requires_pufcsv
def test_compatible_data(cps_subsample, puf_subsample,
                         allparams, reform_xx,
                         tc_objs, allparams_batch):
    """
    Test that the compatible_data attribute in current_law_policy.json
    is accurate by implementing the min and max values of each parameter
    as reforms and ensuring that revenue differs from baseline when for
    at least one of these reforms when using datasets marked compatible
    and does not differ when using datasets marked as incompatible.
    """
    # pylint: disable=too-many-arguments,too-many-locals
    # pylint: disable=too-many-statements,too-many-branches

    # Get taxcalc objects from tc_objs fixture
    rec_xx, c_xx, puftest = tc_objs

    # These parameters are exempt because they are not active under
    # current law and activating them would deactivate other parameters.
    exempt_from_testing = ['_CG_ec', '_CG_reinvest_ec_rt']

    # Loop through the parameters in allparams_batch
    errmsg = 'ERROR: {} not {} for {}\n'
    errors = ''
    for pname in allparams_batch:
        param = allparams_batch[pname]
        max_listed = param['range']['max']
        # handle links to other params or self
        if isinstance(max_listed, six.string_types):
            if max_listed == 'default':
                max_val = param['value'][-1]
            else:
                max_val = allparams[max_listed]['value'][0]
        if not isinstance(max_listed, six.string_types):
            if isinstance(param['value'][0], list):
                max_val = [max_listed] * len(param['value'][0])
            else:
                max_val = max_listed
        min_listed = param['range']['min']
        if isinstance(min_listed, six.string_types):
            if min_listed == 'default':
                min_val = param['value'][-1]
            else:
                min_val = allparams[min_listed]['value'][0]
        if not isinstance(min_listed, six.string_types):
            if isinstance(param['value'][0], list):
                min_val = [min_listed] * len(param['value'][0])
            else:
                min_val = min_listed
        # create reform dictionaries
        max_reform = copy.deepcopy(reform_xx)
        min_reform = copy.deepcopy(reform_xx)
        max_reform[XX_YEAR][str(pname)] = [max_val]
        min_reform[XX_YEAR][str(pname)] = [min_val]
        # assess whether max reform changes results
        if puftest:
            rec_yy = Records(data=puf_subsample)
        else:
            rec_yy = Records.cps_constructor(data=cps_subsample)
        p_yy = Policy()
        p_yy.implement_reform(max_reform)
        c_yy = Calculator(policy=p_yy, records=rec_yy, verbose=False)
        c_yy.advance_to_year(TEST_YEAR)
        c_yy.calc_all()
        if pname.startswith('_BEN') and pname.endswith('_repeal'):
            max_reform_change = (
                c_yy.weighted_total('benefit_cost_total') -
                c_xx.weighted_total('benefit_cost_total')
            )
        else:
            max_reform_change = (
                c_yy.weighted_total('combined') -
                c_xx.weighted_total('combined')
            )
        min_reform_change = 0
        # assess whether min reform changes results, if max reform did not
        if max_reform_change == 0:
            p_yy = Policy()
            p_yy.implement_reform(min_reform)
            c_yy = Calculator(policy=p_yy, records=rec_xx)
            c_yy.advance_to_year(TEST_YEAR)
            c_yy.calc_all()
            if pname.startswith('_BEN') and pname.endswith('_repeal'):
                min_reform_change = (
                    c_yy.weighted_total('benefit_cost_total') -
                    c_xx.weighted_total('benefit_cost_total')
                )
            else:
                min_reform_change = (
                    c_yy.weighted_total('combined') -
                    c_xx.weighted_total('combined')
                )
            if min_reform_change == 0 and pname not in exempt_from_testing:
                if puftest:
                    if param['compatible_data']['puf'] is not False:
                        errors += errmsg.format(pname, 'False', 'puf')
                else:
                    if param['compatible_data']['cps'] is not False:
                        errors += errmsg.format(pname, 'False', 'cps')
        if max_reform_change != 0 or min_reform_change != 0:
            if puftest:
                if param['compatible_data']['puf'] is not True:
                    errors += errmsg.format(pname, 'True', 'puf')
            else:
                if param['compatible_data']['cps'] is not True:
                    errors += errmsg.format(pname, 'True', 'cps')
    # test failure if any errors
    if errors:
        print(errors)
        assert 'compatible_data' == 'invalid'
