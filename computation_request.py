# This file computes correlations between different gene expression tracks.
#
# Created in Sep. 2017 by Zhe Cui
#

import numpy as np
import pandas as pd
from scipy.stats.stats import pearsonr
from scipy.stats import ttest_ind, fisher_exact, norm
from scipy.io import savemat
from utils import build_obj, build_exp_methy_obj, add_to_block, format_expression_block_data, build_exp_singlegene_obj
from requests import get_methy_data, get_block_data, get_gene_data, get_sample_counts

import urllib2
import json
import itertools
import math


def block_to_expression_map(block_type):
    block_map = {
        "P1_Hc_Jx_H3K27me3_ATM_pooled_narrowPeak" : "p1hc",
        "P1_Hc_fAtoh1_GFP_filt_narrowPeak" : "p1hc",
        "P1_Sc_Lfng_GFP_ppr_narrowPeak" : "p1sc",
        "P1_Sc_Lfng_H3K27me3_ATM_pooled_narrowPeak" : "p1sc",
        "P6_Hc_fAtoh1_GFP_ppr_IDR0_narrowPeak": "p6hc",
        "P6_Sc_Lfng_GFP_ppr_narrowPeak" : "p6sc",
        "P6_Sc_Lfng_H3K27me3_ATM_pooled_narrowPeak" : "p6sc",
        "p1hc_h3k9ac_peaks_merged" : "p1hc",
        "p1sc_h3k9ac_peaks_merged" : "p1sc",
        "p6hc_h3k9ac_peaks_merged" : "p6hc",
        "p6sc_h3k9ac_peaks_merged" : "p6sc"
    }

    if block_type in block_map:
        return block_map[block_type]
    else:
        return None



def ttest_block_expression(exp_data, block_data, exp_datasource,
                           datasource_types, promoter=5000):

    ttest_res = []
    gene_expression_block = dict()
    gene_expression_nonblock = dict()

    # loop through block of different tissue types
    for block_type, block_dataframe in block_data.items():
        if not block_dataframe.empty:
            # loop through each start, end in the block
            # only with tissues that align with block types
            # get tissue type from block id
            # for chipseq data, the first four letters are the same
            tissue_type = block_to_expression_map(block_type)
            exp_types = [tissue_type + "1", tissue_type + "2"]
            if tissue_type == "p1hc":
                exp_types.append(tissue_type + "3")
                        
            gene_expression_block[block_type] = pd.DataFrame(columns=exp_types)
            gene_expression_nonblock[block_type] = pd.DataFrame(
                columns=exp_types)
            for ind, row in block_dataframe.iterrows():
                start = row["start"]
                end = row["end"]
                exp_block = pd.DataFrame(columns=exp_types)
                exp_block = exp_block.append(exp_data[(start <= exp_data[
                    "start"] - promoter) & (exp_data["start"] - promoter <= end)][exp_types])
                exp_block = exp_block.append(exp_data[(start <= exp_data["end"])
                                                      & (exp_data["end"] <= end)][exp_types])
                exp_block = exp_block.append(exp_data[(exp_data["start"] - promoter <=
                                                       start) & (start <= exp_data["end"])][exp_types])

                exp_block = exp_block.append(exp_data[((exp_data["start"] - promoter <=
                                                        end) & (end <= exp_data["end"]))][exp_types])

                exp_nonblock = exp_data[(exp_data["end"] < start) | (exp_data[
                    "start"] - promoter > end)][exp_types]
                
                gene_expression_block[block_type] = gene_expression_block[
                    block_type].append(exp_block)
                gene_expression_nonblock[block_type] = gene_expression_nonblock[
                    block_type].append(exp_nonblock)

    pd_block = pd.DataFrame(datasource_types)
    pd_expression = pd.DataFrame(exp_datasource)

    # calculate t test between block and non-block gene expression of the same
    # tissue type
    for block_type, gene_per_block_exp in gene_expression_block.items():

        gene_per_nonblock_exp = gene_expression_nonblock[block_type]
        for exp_type in gene_per_block_exp:
            gene_block_exp = gene_per_block_exp[exp_type]
            if gene_block_exp.empty:
                continue
            gene_nonblock_exp = gene_per_nonblock_exp[exp_type]

            t_value, p_value = ttest_ind(gene_block_exp, gene_nonblock_exp,
                                         equal_var=False)
            print "block:" + block_type + ", gene:" + exp_type
            print p_value
            gene_ds = json.loads(pd_expression.loc[pd_expression['id'] ==
                                                   exp_type].to_json(orient='records')[1:-1])
            block_ds = json.loads(pd_block.loc[pd_block['id'] ==
                                               block_type].to_json(orient='records')[1:-1])

            data = format_expression_block_data(
                gene_block_exp, gene_nonblock_exp)

            ttest_obj = build_obj('t-test', 'expression', 'block', False,
                                  gene_ds, block_ds, t_value, p_value, data)

            ttest_res.append(ttest_obj)

    ttest_res = sorted(ttest_res, key=lambda x: x['value'], reverse=True)

    return ttest_res


def block_overlap_percent(data_sources, block_data, start_seq, end_seq):
    block_overlap = []
    if not block_data:
        return block_overlap
        
    for data_source_one, data_source_two in itertools.combinations(
            data_sources, 2):
        tissue_type_one = data_source_one["id"]
        tissue_type_two = data_source_two["id"]

        if tissue_type_one not in block_data or tissue_type_two not in block_data:
            continue

        block_tissue_one = block_data[tissue_type_one]
        block_tissue_two = block_data[tissue_type_two]

        block_one_ind = 0
        block_two_ind = 0
        block_one_len = len(block_tissue_one['start'])
        block_two_len = len(block_tissue_two['start'])

        overlap_region = []
        block_one_region = []
        block_two_region = []

        # calculate regions for each of the block tissues separately
        # union regions should be the sum of these regions minus overlap region
        for start, end in zip(block_tissue_one['start'], block_tissue_one[
                'end']):
            if min(end, float(end_seq)) > max(start, float(start_seq)):
                block_one_region.append(min(end, float(end_seq)) -
                                        max(start, float(start_seq)))

        for start, end in zip(block_tissue_two['start'], block_tissue_two[
                'end']):
            if min(end, float(end_seq)) > max(start, float(start_seq)):
                block_two_region.append(min(end, float(end_seq)) -
                                        max(start, float(start_seq)))

        while block_one_ind < block_one_len and block_two_ind < block_two_len:
            tissue_one_start = max(float(start_seq), block_tissue_one['start'][
                block_one_ind])
            tissue_two_start = max(float(start_seq), block_tissue_two['start'][
                block_two_ind])
            tissue_one_end = min(float(end_seq), block_tissue_one['end'][
                block_one_ind])
            tissue_two_end = min(float(end_seq), block_tissue_two['end'][
                block_two_ind])

            # there is an overlap
            if tissue_one_start <= tissue_two_start < tissue_one_end or \
               tissue_one_start < tissue_two_end <= tissue_one_end or \
               tissue_two_start <= tissue_one_start < tissue_two_end or \
               tissue_two_start < tissue_one_end <= tissue_two_end:
                common_end = min(tissue_two_end, tissue_one_end)
                common_start = max(tissue_one_start, tissue_two_start)
                if common_end > common_start:
                    overlap_region.append(common_end - common_start)
                if tissue_two_end < tissue_one_end:
                    block_two_ind += 1
                else:
                    block_one_ind += 1
            # block tissue two is larger
            elif tissue_two_start >= tissue_one_end:
                block_one_ind += 1
            # block tissue one is larger
            elif tissue_one_start >= tissue_two_end:
                block_two_ind += 1

        overlap = sum(overlap_region)
        union = sum(block_one_region) + sum(block_two_region) - overlap
        block_one_only = max(sum(block_one_region) - overlap, 0)
        block_two_only = max(sum(block_two_region) - overlap, 0)
        non_block = max(int(end_seq) - int(start_seq) - union, 0)
        fisher_table = np.array([[overlap, block_one_only],
                                 [block_two_only, non_block]])

        odds_ratio, p_value = fisher_exact(fisher_table)
        if math.isnan(odds_ratio):
            continue
        print 'p value is ' + str(p_value)
        print 'odds ratio is ' + str(odds_ratio)
        overlap_percent = 0.0 if union == 0.0 else overlap * 1.0 / union
        overlap_obj = build_obj('overlap', 'peaks', 'peaks', False,
                                data_source_one, data_source_two,
                                overlap_percent, p_value)
        block_overlap.append(overlap_obj)

    block_overlap = sorted(block_overlap, key=lambda x: x['value'],
                           reverse=True)
    print 'overlap done!'
    return block_overlap


def expression_methy_correlation(exp_data, datasource_gene_types,
                                 datasource_methy_types,
                                 methy_data, downstream=3000, upstream=1000):
    print "expression_methy_correlation"
    corr_res = []

    # check if the data is empty
    if exp_data.empty or methy_data.empty:
        return corr_res

    methy_types = [datasource_type["name"] for datasource_type in
                   datasource_methy_types]

    methy_mean = pd.DataFrame(columns=methy_types)

    for i in range(len(exp_data)):
        exp_start = exp_data.iloc[i]['start'] - downstream
        exp_end = exp_data.iloc[i]['end'] + upstream
        methy_filtered = methy_data[((exp_start <= methy_data.start) & (
            methy_data.start <= exp_end)) | ((exp_start <= methy_data.end)
                                             & (methy_data.end <= exp_end))]
        mean = methy_filtered[methy_types].mean().fillna(0)
        methy_mean = methy_mean.append(mean,
                                       ignore_index=True)

    for datasource_gene_type in datasource_gene_types:
        tissue_type = datasource_gene_type["id"]
        expression = exp_data[tissue_type]

        for datasource_methy_type in datasource_methy_types:
            methy_type = datasource_methy_type["id"]

            correlation_coefficient = pearsonr(methy_mean[methy_type],
                                               expression)

            if math.isnan(correlation_coefficient[0]):
                continue
            print correlation_coefficient[0]

            # format the data into list of json objects for plots
            data = format_exp_methy_output(expression, methy_mean[
                methy_type], datasource_gene_type["name"], datasource_methy_type["name"])

            data_range = {
                'attr-one': [min(expression),
                             max(expression)],
                'attr-two': [min(methy_mean[methy_type]),
                             max(methy_mean[methy_type])]
            }
            corr_obj = build_exp_methy_obj('correlation', 'expression',
                                           'methylation', True, datasource_gene_type["name"],
                                           datasource_methy_type["name"],
                                           correlation_coefficient[0],
                                           correlation_coefficient[1],
                                           data=data, ranges=data_range)
            corr_res.append(corr_obj)
            corr_res = sorted(corr_res, key=lambda x: x['value'],
                              reverse=True)

    return corr_res


def format_exp_methy_output(attr1, attr2, type1, type2):
    data = []
    for exp, methy in zip(attr1, attr2):
        point = dict()
        point[type1] = exp
        point[type2] = methy
        data.append(point)

    return data


def ttest_expression_per_gene(gene_types, exp_data, chromosome, start_seq, end_seq):
    print "ttest per single gene!"

    sample_counts = get_sample_counts(
        gene_types, start_seq, end_seq, chromosome)

    ttest_results = []

    if exp_data.empty or not sample_counts:
        return ttest_results

    gene_pairs = [["p1hc1", "p1hc2", "p1hc3"], ["p1sc3", "p1sc2", "p1sc1"], ["p6sc2", "p6sc3"], ["p6hc2", "p6hc1"]]
    for gene_pair in gene_pairs:
        exp1 = gene_pair[0]
        exp2 = gene_pair[1]
        data_source_one = [
            element for element in gene_types if element["id"] == exp1][0]
        data_source_two = [
            element for element in gene_types if element["id"] == exp2][0]

        for index, row in exp_data.iterrows():

            one = row[exp1]
            two = row[exp2]

            variance_threshold = 0.05 * 0.95

            var_one = variance_threshold if (
                one * (1 - one)) < variance_threshold else (one * (1 - one))

            var_two = variance_threshold if (
                two * (1 - two)) < variance_threshold else (two * (1 - two))

            denominator = math.sqrt(var_one / sample_counts[exp1][0] +
                                    var_two / sample_counts[exp2][0])

            ttest_value = (one - two) / denominator

            p_value = 1 - norm.cdf(ttest_value)

            data = [{
                "type": data_source_one["name"],
                "value": one
            }, {
                "type": data_source_two["name"],
                "value": two
            }]

            corr_obj = build_exp_singlegene_obj('Binomial test difference in proportions', 'expression',                                        'expression', True, data_source_one,
                                                data_source_two, ttest_value, pvalue=p_value, gene=row['gene'], data=data)
            ttest_results.append(corr_obj)

    ttest_results = sorted(ttest_results, key=lambda x: x['value'],
                           reverse=True)

    return ttest_results


def methy_correlation(methy_raw, methylation_diff_types):
    methy_corr_res = []
    if methy_raw.empty:
        return methy_corr_res
    # loop through normal/tumor of each tissue type
    for data_source_one, data_source_two in itertools.combinations(
            methylation_diff_types, 2):
        type1 = data_source_one["name"]
        type2 = data_source_two["name"]
        # if type1.split("_")[0] != type2.split("_")[0] or type1 not in methy_raw.columns or type2 not in methy_raw.columns:
        #     continue

        correlation_coefficient = pearsonr(methy_raw[type1], methy_raw[
            type2])

        print type1, type2
        data_range = {
            'attr-one': [min(methy_raw[type1]), max(methy_raw[type1])],
            'attr-two': [min(methy_raw[type2]), max(methy_raw[type2])]
        }
        corr_obj = build_obj('correlation', 'signal',
                             'signal', True, data_source_one,
                             data_source_two,
                             correlation_coefficient[0],
                             correlation_coefficient[1],
                             ranges=data_range)
        methy_corr_res.append(corr_obj)
    methy_corr_res = sorted(methy_corr_res, key=lambda x: x['value'],
                            reverse=True)
    return methy_corr_res


def average_expression(data, gene_pairs):
    average_df = pd.DataFrame(data)
    for gene, samples in gene_pairs.iteritems():
        average_df['avg ' + gene] = average_df[samples].mean(axis=1)
        average_df = average_df.drop(columns=samples)

    print(average_df)
    return average_df


def computation_request(start_seq, end_seq, chromosome, gene_name,                                      measurements=None):
    # extract data from measurements
    gene_types = []
    block_types = []

    methylation_types = []
    methylation_diff_types = []
    # categorize measurements into different types
    for measurement in measurements:
        data_obj = {
            "id": measurement["id"],
            "name": measurement["name"],
            "datasourceId": measurement["datasourceId"]
        }
        if measurement["defaultChartType"] == "scatterplot":
            gene_types.append(data_obj)
        elif measurement["defaultChartType"] == "block":
            block_types.append(data_obj)
        elif measurement["defaultChartType"] == "line":
            # for chipseq data, we only have methylation data
            methylation_types.append(data_obj)

    block_data = None
    methy_raw = None
    methy_raw_diff = None
    expression_data = None
    has_block = len(block_types) > 0
    has_methy = len(methylation_types) > 0
    has_methy_diff = len(methylation_diff_types) > 0
    has_gene = len(gene_types) > 0

    expression_data = get_gene_data(start_seq, end_seq, chromosome,
                                    gene_types)

    gene_pairs = {
        "p1hc" : ["p1hc1", "p1hc2", "p1hc3"], 
        "p1sc" : ["p1sc3", "p1sc2", "p1sc1"], 
        "p6sc" : ["p6sc2", "p6sc3"], 
        "p6hc" : ["p6hc2", "p6hc1"]
    }

    average_gene_types = ["avg p1hc", "avg p1sc", "avg p6sc", "avg p6hc"]

    average_expression_data = average_expression(expression_data, gene_pairs)

    if expression_data.empty:
        has_gene = False                        

    per_gene_ttest = ttest_expression_per_gene(gene_types, expression_data,
                                               chromosome, start_seq, end_seq)

    yield per_gene_ttest

    if has_block:
        block_data = get_block_data(
            start_seq, end_seq, chromosome, block_types)

        # block overlap percentage
        block_overlap = block_overlap_percent(block_types, block_data,
                                              start_seq, end_seq)
        yield block_overlap

    # There's not methy_diff data for chipSeq dataset
    if has_methy_diff:
        methy_raw_diff = get_methy_data(start_seq, end_seq, chromosome,
                                        methylation_diff_types)

        methy_diff_corr_res = methy_diff_correlation(
            methy_raw_diff, methylation_diff_types)

        yield methy_diff_corr_res

    if has_methy:
        methy_raw = get_methy_data(start_seq, end_seq, chromosome,
                                   methylation_types)
        methy_corr_res = methy_correlation(methy_raw, methylation_types)

        yield methy_corr_res

    if has_gene:

        corr_list = []
        # pvalue_list = []
        for data_source_one, data_source_two in itertools.combinations(
                average_gene_types, 2):
            exp1 = data_source_one
            exp2 = data_source_two

            if exp1 not in average_expression_data.columns or exp2 not in average_expression_data.columns:
                continue

            col_one = average_expression_data[exp1]
            col_two = average_expression_data[exp2]

            data = format_exp_methy_output(col_one, col_two, "Expression " + exp1.split(" ")[1],  'Expression ' + exp2.split(" ")[1])

            data_range = {
                'attr-one': [min(col_one),
                            max(col_one)],
                'attr-two': [min(col_two),
                            max(col_two)]
            }

            correlation_coefficient = pearsonr(col_one, col_two)
            corr_obj = build_exp_methy_obj('correlation', 'expression',
                                       'expression', True, "Expression " + exp1.split(" ")[1],
                                       'Expression ' + exp2.split(" ")[1],
                                       correlation_coefficient[0],
                                       correlation_coefficient[1],
                                       data=data, ranges=data_range)

            corr_list.append(corr_obj)

            t_value, p_value = ttest_ind(col_one, col_two,
                                         equal_var=False)
            # ttest_obj = build_obj('t-test', 'expression', 'expression', True,
            #                       data_source_one, data_source_two, t_value,
            #                       p_value)
            # pvalue_list.append(ttest_obj)

        # pvalue_list = sorted(pvalue_list, key=lambda x: x['value'],
        #                      reverse=True)
        # yield pvalue_list

        corr_list = sorted(corr_list, key=lambda x: x['value'],
                           reverse=True)
        yield corr_list

    if has_gene and has_block:
        # gene expression and block independency test
        ttest_block_exp = ttest_block_expression(average_expression_data, block_data,
                                                 gene_types, block_types)
        yield ttest_block_exp

    if has_gene and has_methy:
        # correlation between methylation and gene expression
        # with the same tissue type
        corr_methy_gene = expression_methy_correlation(average_expression_data, gene_types, methylation_types,
                                                       methy_raw)

        yield corr_methy_gene
