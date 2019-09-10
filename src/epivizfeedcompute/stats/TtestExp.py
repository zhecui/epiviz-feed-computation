import math
import logging
import itertools
from .BaseStats import BaseStats

class TtestExp(BaseStats):
    '''
    Class for computing ttest on gene expressions 
    '''
    def __init__(self, measurements, pval_threshold):
        super(TtestGene, self).__init__(measurements, pval_threshold)
        self.measurements = self.filter(measurements)

    def compute_stat(self, data1, data2, params=None):
        variance_threshold = 0.05 * 0.95
        var_one = math.max(variance_threshold, (data1 * (1 - data1)))
        var_two = math.max(variance_threshold, (data2 * (1 - data2)))
        denominator = math.sqrt(var_one / params["sample_count_normal"] + var_two / params["sample_count_tumor"])
        ttest_value = (data1 - data2) / denominator
        p_value = 1 - norm.cdf(abs(ttest_value))
        return ttest_value, p_value

    def compute(self, chr, start, end, params):
        msets = combinations(self.measurements, 2)
        results = []
        
        for (m1, m2) in msets:
            params = {"sample_count_normal": m1.annotation["sample_count"], "sample_count_tumor": m2.annotation["sample_count"]}
            data1, data2 = self.get_transform_data([m1, m2])
            for i in range(len(data1)):
                value, pvalue = self.compute_stat(data1[i], data2[i], params)
                if pvalue <= self.pval_threshold:
                    results.append(
                        {
                            'measurements': (m1, m2),
                            'test': 'ttest',
                            'value': value,
                            'pvalue': pvalue
                        }
                    )

        sorted_results = sorted(results, key=lambda x: x['value'], reverse=True)

        return self.toDataFrame(sorted_results)