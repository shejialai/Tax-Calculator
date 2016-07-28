import os
import sys
import json
import numpy as np
import pandas as pd
import tempfile
import copy
import pytest
CUR_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(CUR_PATH, '..', '..'))
from taxcalc import Policy, Records, Calculator, Behavior, Consumption
from taxcalc import create_distribution_table, create_difference_table

# use 1991 PUF-like data to emulate current puf.csv, which is private
TAXDATA_PATH = os.path.join(CUR_PATH, '..', 'altdata', 'puf91taxdata.csv.gz')
TAXDATA = pd.read_csv(TAXDATA_PATH, compression='gzip')
WEIGHTS_PATH = os.path.join(CUR_PATH, '..', 'altdata', 'puf91weights.csv.gz')
WEIGHTS = pd.read_csv(WEIGHTS_PATH, compression='gzip')

IRATES = {1991: 0.015, 1992: 0.020, 1993: 0.022, 1994: 0.020, 1995: 0.021,
          1996: 0.022, 1997: 0.023, 1998: 0.024, 1999: 0.024, 2000: 0.024,
          2001: 0.024, 2002: 0.024, 2003: 0.024, 2004: 0.024}

WRATES = {1991: 0.0276, 1992: 0.0419, 1993: 0.0465, 1994: 0.0498,
          1995: 0.0507, 1996: 0.0481, 1997: 0.0451, 1998: 0.0441,
          1999: 0.0437, 2000: 0.0435, 2001: 0.0430, 2002: 0.0429,
          2003: 0.0429, 2004: 0.0429}

RAWINPUTFILE_FUNITS = 4
RAWINPUTFILE_YEAR = 2015
RAWINPUTFILE_CONTENTS = (
    'RECID,MARS\n'
    '1,2\n'
    '2,1\n'
    '3,4\n'
    '4,6\n'
)


@pytest.yield_fixture
def rawinputfile():
    """
    Temporary input file that contains minimum required input varaibles.
    """
    ifile = tempfile.NamedTemporaryFile(mode='a', delete=False)
    ifile.write(RAWINPUTFILE_CONTENTS)
    ifile.close()
    # must close and then yield for Windows platform
    yield ifile
    if os.path.isfile(ifile.name):
        try:
            os.remove(ifile.name)
        except OSError:
            pass  # sometimes we can't remove a generated temporary file


@pytest.yield_fixture
def policyfile():
    txt = """{"_almdep": {"value": [7150, 7250, 7400]},
             "_almsep": {"value": [40400, 41050]},
             "_rt5": {"value": [0.33 ]},
             "_rt7": {"value": [0.396]}}"""
    f = tempfile.NamedTemporaryFile(mode="a", delete=False)
    f.write(txt + "\n")
    f.close()
    # Must close and then yield for Windows platform
    yield f
    os.remove(f.name)


def test_make_Calculator():
    parm = Policy()
    assert parm.current_year == 2013
    recs = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    consump = Consumption()
    consump.update_consumption({2014: {'_MPC_e20400': [0.05]}})
    assert consump.current_year == 2013
    calc = Calculator(policy=parm, records=recs, consumption=consump)
    assert calc.current_year == 2013
    # test incorrect Calculator instantiation:
    with pytest.raises(ValueError):
        calc = Calculator(policy=None, records=recs)
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=None)
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, behavior=list())
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, growth=list())
    with pytest.raises(ValueError):
        calc = Calculator(policy=parm, records=recs, consumption=list())


def test_make_Calculator_deepcopy():
    parm = Policy()
    recs = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc1 = Calculator(policy=parm, records=recs)
    calc2 = copy.deepcopy(calc1)
    assert isinstance(calc2, Calculator)


def test_make_Calculator_with_policy_reform():
    # create a Policy object and apply a policy reform
    policy2 = Policy()
    reform2 = {2013: {'_II_em': np.array([4000]), '_II_em_cpi': False,
                      '_STD_Aged': [[1600, 1300, 1300, 1600, 1600, 1300]],
                      "_STD_Aged_cpi": False}}
    policy2.implement_reform(reform2)
    # create a Calculator object using this policy-reform
    puf = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc2 = Calculator(policy=policy2, records=puf)
    # check that Policy object embedded in Calculator object is correct
    assert calc2.current_year == 2013
    assert calc2.policy.II_em == 4000
    assert np.allclose(calc2.policy._II_em,
                       np.array([4000] * Policy.DEFAULT_NUM_YEARS),
                       atol=0.01, rtol=0.0)
    exp_STD_Aged = [[1600, 1300, 1300,
                     1600, 1600, 1300]] * Policy.DEFAULT_NUM_YEARS
    assert np.allclose(calc2.policy._STD_Aged,
                       np.array(exp_STD_Aged),
                       atol=0.01, rtol=0.0)
    assert np.allclose(calc2.policy.STD_Aged,
                       np.array([1600, 1300, 1300, 1600, 1600, 1300]),
                       atol=0.01, rtol=0.0)


def test_make_Calculator_with_multiyear_reform():
    # create a Policy object and apply a policy reform
    policy3 = Policy()
    reform3 = {2015: {}}
    reform3[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform3[2015]['_II_em'] = [5000, 6000]  # reform values for 2015 and 2016
    reform3[2015]['_II_em_cpi'] = False
    policy3.implement_reform(reform3)
    # create a Calculator object using this policy-reform
    puf = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc3 = Calculator(policy=policy3, records=puf)
    # check that Policy object embedded in Calculator object is correct
    assert calc3.current_year == 2013
    assert calc3.policy.II_em == 3900
    assert calc3.policy.num_years == Policy.DEFAULT_NUM_YEARS
    exp_II_em = [3900, 3950, 5000] + [6000] * (Policy.DEFAULT_NUM_YEARS - 3)
    assert np.allclose(calc3.policy._II_em,
                       np.array(exp_II_em),
                       atol=0.01, rtol=0.0)
    calc3.increment_year()
    calc3.increment_year()
    assert calc3.current_year == 2015
    assert np.allclose(calc3.policy.STD_Aged,
                       np.array([1600, 1300, 1600, 1300, 1600, 1300]),
                       atol=0.01, rtol=0.0)


def test_make_Calculator_with_reform_after_start_year():
    # create Policy object using custom indexing rates
    irates = {2013: 0.01, 2014: 0.01, 2015: 0.02, 2016: 0.01, 2017: 0.03}
    parm = Policy(start_year=2013, num_years=len(irates),
                  inflation_rates=irates)
    # specify reform in 2015, which is two years after Policy start_year
    reform = {2015: {}, 2016: {}}
    reform[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform[2015]['_II_em'] = [5000]
    reform[2016]['_II_em'] = [6000]
    reform[2016]['_II_em_cpi'] = False
    parm.implement_reform(reform)
    recs = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc = Calculator(policy=parm, records=recs)
    # compare actual and expected parameter values over all years
    assert np.allclose(calc.policy._STD_Aged,
                       np.array([[1500, 1200, 1200, 1500, 1500, 1200],
                                 [1550, 1200, 1200, 1550, 1550, 1200],
                                 [1600, 1300, 1600, 1300, 1600, 1300],
                                 [1632, 1326, 1632, 1326, 1632, 1326],
                                 [1648, 1339, 1648, 1339, 1648, 1339]]),
                       atol=0.5, rtol=0.0)
    assert np.allclose(calc.policy._II_em,
                       np.array([3900, 3950, 5000, 6000, 6000]),
                       atol=0.001, rtol=0.0)
    # compare actual and expected values for 2015
    calc.increment_year()
    calc.increment_year()
    assert calc.current_year == 2015
    assert np.allclose(calc.policy.II_em,
                       5000,
                       atol=0.0, rtol=0.0)
    assert np.allclose(calc.policy.STD_Aged,
                       np.array([1600, 1300, 1600, 1300, 1600, 1300]),
                       atol=0.0, rtol=0.0)


def test_Calculator_advance_to_year():
    policy = Policy()
    puf = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc = Calculator(policy=policy, records=puf)
    calc.advance_to_year(2016)
    assert calc.current_year == 2016
    with pytest.raises(ValueError):
        calc.advance_to_year(2015)


def test_make_Calculator_user_mods_with_cpi_flags(policyfile):
    with open(policyfile.name) as pfile:
        policy = json.load(pfile)
    ppo = Policy(parameter_dict=policy, start_year=1991,
                 num_years=len(IRATES), inflation_rates=IRATES,
                 wage_growth_rates=WRATES)
    rec = Records(data=TAXDATA, start_year=1991)
    calc = Calculator(policy=ppo, records=rec)
    user_mods = {1991: {"_almdep": [7150, 7250, 7400],
                        "_almdep_cpi": True,
                        "_almsep": [40400, 41050],
                        "_almsep_cpi": False,
                        "_rt5": [0.33],
                        "_rt7": [0.396]}}
    calc.policy.implement_reform(user_mods)
    # compare actual and expected values
    inf_rates = [IRATES[1991 + i] for i in range(0, Policy.DEFAULT_NUM_YEARS)]
    exp_almdep = Policy.expand_array(np.array([7150, 7250, 7400]),
                                     inflate=True,
                                     inflation_rates=inf_rates,
                                     num_years=Policy.DEFAULT_NUM_YEARS)
    act_almdep = getattr(calc.policy, '_almdep')
    assert np.allclose(act_almdep,
                       exp_almdep,
                       atol=0.01, rtol=0.0)
    exp_almsep_values = [40400] + [41050] * (Policy.DEFAULT_NUM_YEARS - 1)
    exp_almsep = np.array(exp_almsep_values)
    act_almsep = getattr(calc.policy, '_almsep')
    assert np.allclose(act_almsep,
                       exp_almsep,
                       atol=0.01, rtol=0.0)


def test_make_Calculator_raises_on_no_policy():
    rec = Records(data=TAXDATA, weights=WEIGHTS, start_year=2013)
    with pytest.raises(ValueError):
        calc = Calculator(records=rec)


def test_Calculator_attr_access_to_policy():
    policy = Policy()
    puf = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc = Calculator(policy=policy, records=puf)
    assert hasattr(calc.records, 'c01000')
    assert hasattr(calc.policy, '_AMT_Child_em')
    assert hasattr(calc, 'policy')


def test_Calculator_create_distribution_table():
    policy = Policy()
    puf = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc = Calculator(policy=policy, records=puf)
    calc.calc_all()
    dist_labels = ['Returns', 'AGI', 'Standard Deduction Filers',
                   'Standard Deduction', 'Itemizers',
                   'Itemized Deduction', 'Personal Exemption',
                   'Taxable Income', 'Regular Tax', 'AMTI', 'AMT Filers',
                   'AMT', 'Tax before Credits', 'Non-refundable Credits',
                   'Tax before Refundable Credits', 'Refundable Credits',
                   'Individual Income Tax Liabilities',
                   'Payroll Tax Liablities',
                   'Combined Payroll and Individual Income Tax Liabilities']
    dt1 = create_distribution_table(calc.records,
                                    groupby="weighted_deciles",
                                    result_type="weighted_sum")
    dt1.columns = dist_labels
    dt2 = create_distribution_table(calc.records,
                                    groupby="small_income_bins",
                                    result_type="weighted_avg")
    assert isinstance(dt1, pd.DataFrame)
    assert isinstance(dt2, pd.DataFrame)


def test_Calculator_mtr():
    puf = Records(TAXDATA, weights=WEIGHTS, start_year=2009)
    calc = Calculator(policy=Policy(), records=puf)
    recs_pre_e00200p = copy.deepcopy(calc.records.e00200p)
    (mtr_FICA, mtr_IIT, mtr_combined) = calc.mtr(income_type_str='e00200p',
                                                 zero_out_calculated_vars=True)
    recs_post_e00200p = copy.deepcopy(calc.records.e00200p)
    assert np.allclose(recs_post_e00200p, recs_pre_e00200p)
    assert type(mtr_combined) == np.ndarray
    assert np.array_equal(mtr_combined, mtr_FICA) is False
    assert np.array_equal(mtr_FICA, mtr_IIT) is False
    with pytest.raises(ValueError):
        (_, _, mtr_combined) = calc.mtr(income_type_str='bad_income_type')
    (_, _, mtr_combined) = calc.mtr(income_type_str='e00650',
                                    negative_finite_diff=True)
    assert type(mtr_combined) == np.ndarray
    (_, _, mtr_combined) = calc.mtr(income_type_str='e00900p')
    assert type(mtr_combined) == np.ndarray
    (_, _, mtr_combined) = calc.mtr(income_type_str='e01700')
    assert type(mtr_combined) == np.ndarray


def test_Calculator_create_difference_table():
    # create current-law Policy object and use to create Calculator calc1
    policy1 = Policy()
    puf1 = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc1 = Calculator(policy=policy1, records=puf1)
    calc1.calc_all()
    # create policy-reform Policy object and use to create Calculator calc2
    policy2 = Policy()
    reform = {2013: {'_II_rt7': [0.45]}}
    policy2.implement_reform(reform)
    puf2 = Records(data=TAXDATA, weights=WEIGHTS, start_year=2009)
    calc2 = Calculator(policy=policy2, records=puf2)
    # create difference table and check that it is a Pandas DataFrame
    dtable = create_difference_table(calc1.records, calc2.records,
                                     groupby="weighted_deciles")
    assert isinstance(dtable, pd.DataFrame)


def test_Calculator_behavioral_response():
    # calculate AGI assuming no behavioral response to reform
    pol1 = Policy()
    pol1.implement_reform({2013: {'_II_rt7': [0.50]}})
    puf1 = Records(data=TAXDATA, weights=WEIGHTS, start_year=Records.PUF_YEAR)
    beh1 = Behavior()
    calc1 = Calculator(policy=pol1, records=puf1, behavior=beh1)
    assert calc1.records.current_year == Policy.JSON_START_YEAR
    calc1.calc_all()
    agi1 = calc1.records.c00100
    # calulatie AGI assuming behavioral response to reform
    pol2 = Policy()
    pol2.implement_reform({2013: {'_II_rt7': [0.50]}})
    puf2 = Records(data=TAXDATA, weights=WEIGHTS, start_year=Records.PUF_YEAR)
    beh2 = Behavior()
    beh2.update_behavior({2013: {'_BE_sub': [0.4]}})
    assert beh2.has_response()
    calc2 = Calculator(policy=pol2, records=puf2, behavior=beh2)
    assert calc2.records.current_year == Policy.JSON_START_YEAR
    calc2.calc_all()
    agi2 = calc2.records.c00100
    # check that AGI amounts are not the same
    assert np.allclose(agi1, agi2)  # TODO: add 'not' after assert


def test_make_Calculator_increment_years_first():
    # create Policy object with custom indexing rates and policy reform
    irates = {2013: 0.01, 2014: 0.01, 2015: 0.02, 2016: 0.01, 2017: 0.03}
    policy = Policy(start_year=2013, inflation_rates=irates,
                    num_years=len(irates))
    reform = {2015: {}, 2016: {}}
    reform[2015]['_STD_Aged'] = [[1600, 1300, 1600, 1300, 1600, 1300]]
    reform[2015]['_II_em'] = [5000]
    reform[2016]['_II_em'] = [6000]
    reform[2016]['_II_em_cpi'] = False
    policy.implement_reform(reform)
    # create Records object by reading 1991 data and saying it is 2009 data
    puf = Records(TAXDATA, weights=WEIGHTS, start_year=2009)
    # create Calculator object with Policy object as modified by reform
    calc = Calculator(policy=policy, records=puf)
    # compare expected policy parameter values with those embedded in calc
    exp_STD_Aged = np.array([[1500, 1200, 1200, 1500, 1500, 1200],
                             [1550, 1200, 1200, 1550, 1550, 1200],
                             [1600, 1300, 1600, 1300, 1600, 1300],
                             [1632, 1326, 1632, 1326, 1632, 1326],
                             [1648, 1339, 1648, 1339, 1648, 1339]])
    assert np.allclose(calc.policy._STD_Aged,
                       exp_STD_Aged,
                       atol=0.5, rtol=0.0)
    exp_II_em = np.array([3900, 3950, 5000, 6000, 6000])
    assert np.allclose(calc.policy._II_em,
                       exp_II_em,
                       atol=0.5, rtol=0.0)


def test_Calculator_using_nonstd_input(rawinputfile):
    # check Calculator handling of raw, non-standard input data with no aging
    policy = Policy()
    policy.set_year(RAWINPUTFILE_YEAR)  # set policy params to input data year
    nonpuf = Records(data=rawinputfile.name,
                     blowup_factors=None,  # keeps raw data unchanged
                     weights=None,
                     start_year=RAWINPUTFILE_YEAR)  # set raw input data year
    assert nonpuf.dim == RAWINPUTFILE_FUNITS
    calc = Calculator(policy=policy,
                      records=nonpuf,
                      sync_years=False)  # keeps raw data unchanged
    assert calc.current_year == RAWINPUTFILE_YEAR
    calc.calc_all()
    exp_iitax = np.zeros((nonpuf.dim,))
    assert np.allclose(nonpuf._iitax, exp_iitax)
    mtr_fica, _, _ = calc.mtr(wrt_full_compensation=False)
    exp_mtr_fica = np.zeros((nonpuf.dim,))
    exp_mtr_fica.fill(0.153)
    assert np.allclose(mtr_fica, exp_mtr_fica)
