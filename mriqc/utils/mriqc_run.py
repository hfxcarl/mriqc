#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: oesteban
# @Date:   2015-11-19 16:44:27
# @Last Modified by:   oesteban
# @Last Modified time: 2016-11-04 11:01:57

"""
=====
MRIQC
=====
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import os.path as op
from multiprocessing import cpu_count

from argparse import ArgumentParser
from argparse import RawTextHelpFormatter

from mriqc.workflows import core as mwc
from mriqc import __version__, MRIQC_LOG
from mriqc.utils.misc import check_folder


def main():
    from nipype import config as ncfg

    """Entry point"""
    parser = ArgumentParser(description='MRI Quality Control',
                            formatter_class=RawTextHelpFormatter)

    parser.add_argument('-v', '--version', action='version',
                        version='mriqc v{}'.format(__version__))

    parser.add_argument('bids_dir', action='store',
                        help='The directory with the input dataset '
                             'formatted according to the BIDS standard.')
    parser.add_argument('output_dir', action='store',
                        help='The directory where the output files '
                             'should be stored. If you are running group level analysis '
                             'this folder should be prepopulated with the results of the'
                             'participant level analysis.')
    parser.add_argument('analysis_level', action='store',
                        help='Level of the analysis that will be performed. '
                             'Multiple participant level analyses can be run independently '
                             '(in parallel) using the same output_dir.',
                        choices=['participant', 'group'])
    parser.add_argument('--participant_label', '--subject_list', '-S', action='store',
                        help='The label(s) of the participant(s) that should be analyzed. '
                             'The label corresponds to sub-<participant_label> from the '
                             'BIDS spec (so it does not include "sub-"). If this parameter '
                             'is not provided all subjects should be analyzed. Multiple '
                             'participants can be specified with a space separated list.',
                        nargs="*")

    g_input = parser.add_argument_group('mriqc specific inputs')
    g_input.add_argument('-d', '--data-type', action='store', nargs='*',
                         choices=['anat', 'func'], default=['anat', 'func'])
    g_input.add_argument('-s', '--session-id', action='store')
    g_input.add_argument('-r', '--run-id', action='store')
    g_input.add_argument('--nthreads', action='store', default=0,
                         type=int, help='number of threads')
    g_input.add_argument('--n_procs', action='store', default=0,
                         type=int, help='number of threads')
    g_input.add_argument('--write-graph', action='store_true', default=False,
                         help='Write workflow graph.')
    g_input.add_argument('--dry-run', action='store_true', default=False,
                         help='Do not run the workflow.')
    g_input.add_argument('--use-plugin', action='store', default=None,
                         help='nipype plugin configuration file')

    g_input.add_argument('--testing', action='store_true', default=False,
                         help='use testing settings for a minimal footprint')

    g_outputs = parser.add_argument_group('mriqc specific outputs')
    g_outputs.add_argument('-w', '--work-dir', action='store', default=op.join(os.getcwd(), 'work'))
    g_outputs.add_argument('--report-dir', action='store')
    g_outputs.add_argument('--verbose-reports', default=False, action='store_true')

    # ANTs options
    g_ants = parser.add_argument_group('specific settings for ANTs registrations')
    g_ants.add_argument('--ants-nthreads', action='store', type=int,
                        help='number of threads that will be set in ANTs processes')
    g_ants.add_argument('--ants-settings', action='store',
                        help='path to JSON file with settings for ANTS')

    # AFNI head motion correction settings
    g_afni = parser.add_argument_group('specific settings for AFNI head motion correction')
    g_afni.add_argument('--hmc-afni', action='store_true', default=False,
                        help='Use ANFI 3dvolreg for head motion correction (HMC) and '
                             'frame displacement (FD) estimation')
    g_afni.add_argument('--deoblique', action='store_true', default=False,
                        help='Deoblique the functional scans during head motion '
                             'correction preprocessing')
    g_afni.add_argument('--despike', action='store_true', default=False,
                        help='Despike the functional scans during head motion correction '
                             'preprocessing')
    g_afni.add_argument('--start-idx', action='store', type=int,
                        help='Initial volume in functional timeseries that should be '
                             'considered for preprocessing')
    g_afni.add_argument('--stop-idx', action='store', type=int,
                        help='Final volume in functional timeseries that should be '
                             'considered for preprocessing')
    g_afni.add_argument('--correct-slice-timing', action='store_true', default=False,
                        help='Perform slice timing correction')

    opts = parser.parse_args()

    # Build settings dict
    bids_dir = op.abspath(opts.bids_dir)

    # Number of processes
    n_procs = 0
    if opts.nthreads is not None:
        MRIQC_LOG.warn('Option --nthreads has been deprecated in mriqc 0.8.8. '
                       'Please use --n_procs instead.')
        n_procs = opts.nthreads
    if opts.n_procs is not None:
        n_procs = opts.n_procs

    settings = {
        'bids_dir': bids_dir,
        'write_graph': opts.write_graph,
        'testing': opts.testing,
        'hmc_afni': opts.hmc_afni,
        'n_procs': n_procs,
        'output_dir': op.abspath(opts.output_dir),
        'work_dir': op.abspath(opts.work_dir),
        'verbose_reports': opts.verbose_reports or opts.testing
    }


    if opts.hmc_afni:
        settings['deoblique'] = opts.deoblique
        settings['despike'] = opts.despike
        settings['correct_slice_timing'] = opts.correct_slice_timing
        if opts.start_idx:
            settings['start_idx'] = opts.start_idx
        if opts. stop_idx:
            settings['stop_idx'] = opts.stop_idx

    if opts.ants_settings:
        settings['ants_settings'] = opts.ants_settings

    if opts.ants_nthreads:
        settings['ants_nthreads'] = opts.ants_nthreads

    log_dir = op.join(settings['output_dir'], 'logs')

    settings['report_dir'] = opts.report_dir
    if not settings['report_dir']:
        settings['report_dir'] = op.join(settings['work_dir'], 'reports')

    check_folder(settings['output_dir'])
    check_folder(settings['work_dir'])
    check_folder(log_dir)
    check_folder(settings['report_dir'])

    # Set nipype config
    ncfg.update_config({
        'logging': {'log_directory': log_dir, 'log_to_file': True},
        'execution': {'crashdump_dir': log_dir}
    })

    plugin_settings = {'plugin': 'Linear'}
    if opts.use_plugin is not None:
        from yaml import load as loadyml
        with open(opts.use_plugin) as pfile:
            plugin_settings = loadyml(pfile)
    else:
        # Setup multiprocessing
        if settings['n_procs'] == 0:
            settings['n_procs'] = cpu_count()

        if settings['n_procs'] > 1:
            plugin_settings['plugin'] = 'MultiProc'
            plugin_settings['plugin_args'] = {'n_procs': settings['n_procs']}

    MRIQC_LOG.info(
        'Running MRIQC-%s (analysis_level=%s, participant_label=%s)\n\tSettings=%s',
        __version__, opts.analysis_level, opts.participant_label, settings)

    # Set up participant level
    if opts.analysis_level == 'participant':
        for qctype in opts.data_type:
            ms_func = getattr(mwc, 'ms_' + qctype)
            workflow = ms_func(subject_id=opts.participant_label, session_id=opts.session_id,
                               run_id=opts.run_id, settings=settings)
            if workflow is None:
                MRIQC_LOG.warn(
                    '%s QC workflow - no scans were found for the given inputs',
                    'Anatomical' if qctype[:4] == 'anat' else 'Functional')
                continue

            workflow.base_dir = settings['work_dir']
            if settings.get('write_graph', False):
                workflow.write_graph()

            if not opts.dry_run:
                workflow.run(**plugin_settings)

    # Set up group level
    if opts.analysis_level == 'group' or opts.participant_label is None:
        from glob import glob
        from mriqc.reports import group_html
        from mriqc.utils.misc import generate_csv

        reports_dir = check_folder(op.join(settings['output_dir'], 'reports'))

        derivatives_dir = op.join(settings['output_dir'], 'derivatives')
        for qctype in opts.data_type:
            qcjson = op.join(derivatives_dir, '{}*.json'.format(qctype[:4]))

            # If there are no iqm.json files, nothing to do.
            if not qcjson:
                MRIQC_LOG.warn(
                    'Generating group-level report for the "%s" data type - '
                    'no IQM-JSON files were found in "%s"', qctype, derivatives_dir)
                continue

            # If some were found, generate the CSV file and group report
            out_csv = op.join(settings['output_dir'], qctype[:4] + 'MRIQC.csv')
            out_html = op.join(reports_dir, qctype[:4] + '_group.html')
            generate_csv(glob(qcjson), out_csv)
            MRIQC_LOG.info('Summary CSV table has been written to %s', out_csv)
            group_html(out_csv, qctype, out_file=out_html)
            MRIQC_LOG.info('Group HTML report has been written to %s', out_html)

if __name__ == '__main__':
    main()
