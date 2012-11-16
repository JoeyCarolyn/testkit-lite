#!/usr/bin/python
#
# Copyright (C) 2012, Intel Corporation.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms and conditions of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place - Suite 330, Boston, MA 02111-1307 USA.
#
# Authors:
#              Wang, Jing <jing.j.wang@intel.com>
#              Tian, Xu <xux.tian@intel.com>
#              Wei, Zhang <wei.z.zhang@intel.com>
#              Zhang, Huihui <huihuix.zhang@intel.com>
#
# Description:
#   test engine
#

import os
import platform
import time
from datetime import datetime
from shutil import copyfile
from textreport import TestResultsTextReport
import xml.etree.ElementTree as etree
import ConfigParser
from xml.dom import minidom
from tempfile import mktemp
from testkitlite.common.str2 import *
from testkitlite.common.autoexec import shell_exec
from shutil import move
from os import remove

_j = os.path.join
_d = os.path.dirname
_b = os.path.basename
_e = os.path.exists
_abs = os.path.abspath

###############################################################################
class TRunner:

    textreport = TestResultsTextReport()
    """
    Parse the testdefinition.xml files.
    Apply filter for each run.
    Conduct tests execution.
    """
    def __init__(self):
        # dryrun
        self.bdryrun = False
        # result file
        self.resultfile = None
        # external test    
        self.external_test = None
        # filter rules
        self.filter_rules = None
        self.fullscreen = False
        self.resultfiles = set()
        self.core_auto_files = []
        self.core_manual_files = []
        self.core_manual_flag = 0
        self.testsuite_dict = {} 
        self.exe_sequence = []
        self.log = None

    def set_pid_log(self, pid_log):
        self.pid_log = pid_log

    def set_dryrun(self, bdryrun):
        self.bdryrun = bdryrun

    def set_resultfile(self, resultfile):
        self.resultfile = resultfile

    def set_external_test(self, exttest):
        self.external_test = exttest

    def add_filter_rules(self, **kargs):
        """
        kargs:  key:values - "":["",]
        """
        self.filter_rules = kargs

    def set_fullscreen(self, state):
        self.fullscreen = state

    def prepare_run(self, testxmlfile, resultdir=None):
        """
        testxmlfile: target testxml file
        execdir and resultdir: should be the absolute path since TRunner
        is the common lib
        """
        # resultdir is set to current directory by default
        if not resultdir:
            resultdir = os.getcwd()
            
        ok = True
        if ok:
            try:
                filename = testxmlfile
                filename = os.path.splitext(filename)[0]
                if platform.system() == "Linux":
                    filename = filename.split('/')[3]
                else:
                    filename = filename.split('\\')[-2]
                if self.filter_rules["execution_type"] == ["manual"]:
                    resultfile = "%s.manual.xml" % filename
                else:
                    resultfile = "%s.auto.xml" % filename
                resultfile = _j(resultdir, resultfile)
                if not _e(resultdir):
                    os.mkdir(resultdir)
                print "[ analysis testing xml file: %s ]" % resultfile
                try:
                    ep = etree.parse(testxmlfile)
                    suiteparent = ep.getroot()
                    no_test_definition = 1
                    for tf in ep.getiterator('test_definition'):
                        no_test_definition = 0
                    if no_test_definition:
                        suiteparent = etree.Element('test_definition')
                        suiteparent.tail = "\n"
                        for suite in ep.getiterator('suite'):
                            suite.tail = "\n"
                            suiteparent.append(suite)
                    self.apply_filter(suiteparent)
                    try:
                        with open(resultfile, 'w') as output:
                            tree = etree.ElementTree(element=suiteparent)
                            tree.write(output)
                    except IOError, e:
                        print "[ create filtered result file: %s failed, error: %s ]" % (resultfile, e)
                except Exception, e:
                    print e
                    return False
                casefind = etree.parse(resultfile).getiterator('testcase')
                if casefind:
                    file = "%s" % _b(resultfile)
                    file = os.path.splitext(file)[0]
                    testsuite_dict_value_list = []
                    testsuite_dict_add_flag = 0
                    execute_suite_one_way = 1
                    if self.external_test: 
                        parser = etree.parse(resultfile)
                        no_wrtlauncher = 1
                        suite_total_count = 0 
                        suite_wrt_launcher_count = 0
                        for tsuite in parser.getiterator('suite'):
                            suite_total_count += 1
                            if tsuite.get('launcher'):
                                if not tsuite.get('launcher').find('WRTLauncher'):
                                    no_wrtlauncher = 0
                                    suite_wrt_launcher_count += 1
                        if no_wrtlauncher:
                            if self.filter_rules["execution_type"] == ["auto"]:
                                self.core_auto_files.append(resultfile)
                            else:
                                self.core_manual_files.append(resultfile)
                        elif suite_total_count == suite_wrt_launcher_count:
                            testsuite_dict_value_list.append(resultfile) 
                            testsuite_dict_add_flag = 1
                            self.exe_sequence.append(file)
                        else:
                            filename_diff = 1
                            execute_suite_one_way = 0
                            for tsuite in parser.getiterator('suite'):
                                root = etree.Element('test_definition')
                                suitefilename = os.path.splitext(resultfile)[0]
                                suitefilename += ".%s.xml" % filename_diff
                                suitefilename = _j(resultdir, suitefilename)
                                tsuite.tail = "\n"
                                root.append(tsuite)
                                try:
                                    with open(suitefilename, 'w') as output:
                                        tree = etree.ElementTree(element=root)
                                        tree.write(output)
                                except IOError, e:
                                    print "[ create filtered result file: %s failed, error: %s ]" % (suitefilename, e)
                                case_suite_find = etree.parse(suitefilename).getiterator('testcase')
                                if case_suite_find:
                                    if tsuite.get('launcher'):
                                        if tsuite.get('launcher').find('WRTLauncher'):
                                            if self.filter_rules["execution_type"] == ["auto"]:
                                                self.core_auto_files.append(suitefilename)
                                            else:
                                                self.core_manual_files.append(suitefilename)
                                        else:
                                            testsuite_dict_value_list.append(suitefilename) 
                                            if testsuite_dict_add_flag == 0:
                                                self.exe_sequence.append(file)
                                            testsuite_dict_add_flag = 1
                                    else:
                                        if self.filter_rules["execution_type"] == ["auto"]:
                                            self.core_auto_files.append(suitefilename)
                                        else:
                                            self.core_manual_files.append(suitefilename)
                                    self.resultfiles.add(suitefilename)
                                filename_diff += 1
                        if testsuite_dict_add_flag:
                            self.testsuite_dict[file] = testsuite_dict_value_list 
                    else:
                        if self.filter_rules["execution_type"] == ["auto"]:
                            self.core_auto_files.append(resultfile)
                        else:
                            self.core_manual_files.append(resultfile)
                    if execute_suite_one_way:
                        self.resultfiles.add(resultfile)
                        
            except Exception, e:
                print e
                ok &= False
        return ok
            
    def run_and_merge_resultfile(self, start_time, end_time, latest_dir):
        # run core auto cases
        for core_auto_files in self.core_auto_files:
            temp = os.path.splitext(core_auto_files)[0]
            temp = os.path.splitext(temp)[0]
            temp = os.path.splitext(temp)[0]
            
            if self.log:
                self.log = os.path.splitext(self.log)[0]
                self.log = os.path.splitext(self.log)[0]
                self.log = os.path.splitext(self.log)[0]
            if self.log != temp:
                print "[ testing xml: %s.auto.xml ]" % _abs(temp)
            self.log = core_auto_files
            self.execute(core_auto_files, core_auto_files)
            
        # run webAPI cases
        self.execute_external_test(self.testsuite_dict, self.exe_sequence)
        
        # run core manual cases
        self.log = None
        for core_manual_files in self.core_manual_files:
            temp = os.path.splitext(core_manual_files)[0]
            temp = os.path.splitext(temp)[0]
            temp = os.path.splitext(temp)[0]
            
            if self.log:
                self.log = os.path.splitext(self.log)[0]
                self.log = os.path.splitext(self.log)[0]
                self.log = os.path.splitext(self.log)[0]
            if self.log != temp:
                print "[ testing xml: %s.manual.xml ]" % _abs(temp)
            self.log = core_manual_files
            self.execute(core_manual_files, core_manual_files)
            
        mergefile = mktemp(suffix='.xml', prefix='tests.', dir=latest_dir)
        mergefile = os.path.splitext(mergefile)[0]
        mergefile = os.path.splitext(mergefile)[0]
        mergefile = "%s.result" % _b(mergefile)
        mergefile = "%s.xml" % mergefile
        mergefile = _j(latest_dir, mergefile)
        print "[ merge result files into %s ]" % mergefile
        root = etree.Element('test_definition')
        root.tail = "\n"
        totals = set()
        for resultfile in self.resultfiles:
            print "|--[ merge result file: %s ]" % resultfile
            totalfile = os.path.splitext(resultfile)[0]
            totalfile = os.path.splitext(totalfile)[0]
            totalfile = os.path.splitext(totalfile)[0]
            totalfile = "%s.total" % totalfile
            totalfile = "%s.xml" % totalfile
            total_xml = etree.parse(totalfile)
            result_xml = etree.parse(resultfile)
            
            for total_suite in total_xml.getiterator('suite'):
                for total_set in total_suite.getiterator('set'):
                    for result_suite in result_xml.getiterator('suite'):
                        for result_set in result_suite.getiterator('set'):
                            # when total xml and result xml have same suite name and set name
                            if result_set.get('name') == total_set.get('name') and result_suite.get('name') == total_suite.get('name'):
                                # set cases that doesn't have result in result set to N/A
                                # append cases from result set to total set
                                result_case_iterator = result_set.getiterator('testcase')
                                if result_case_iterator:
                                    print "`----[ suite: %s, set: %s, time: %s ]" % (result_suite.get('name'), result_set.get('name'), datetime.today().strftime("%Y-%m-%d_%H_%M_%S"))
                                    for result_case in result_case_iterator:
                                        try:
                                            if not result_case.get('result'):
                                                result_case.set('result', 'N/A')
                                            total_set.append(result_case)
                                        except Exception, e:
                                            print "[ fail to append %s, error: %s ]" % (result_case.get('id'), e)
            total_xml.write(totalfile)
            totals.add(totalfile)
        for total in totals:
            result_xml = etree.parse(total)
            for suite in result_xml.getiterator('suite'):
                suite.tail = "\n"
                root.append(suite)
        try:
            with open(mergefile, 'w') as output:
                tree = etree.ElementTree(element=root)
                tree.write(output)
        except IOError, e:
            print "[ merge result file failed, error: %s ]" % e
        # report the result using xml mode
        print "[ generate result xml: %s ]" % mergefile
        if self.core_manual_flag:
            print "[ all results for core manual cases are N/A, the result file is at %s ]" % mergefile
        
        ep = etree.parse(mergefile)
        rt = ep.getroot()
        environment = etree.Element('environment')
        environment.attrib['device_id'] = "Empty device_id"
        environment.attrib['device_model'] = "Empty device_model"
        environment.attrib['device_name'] = "Empty device_name"
        environment.attrib['firmware_version'] = "Empty firmware_version"
        environment.attrib['host'] = "Empty host"
        environment.attrib['os_version'] = "Empty os_version"
        environment.attrib['resolution'] = "Empty resolution"
        environment.attrib['screen_size'] = "Empty screen_size"
        other = etree.Element('other')
        other.text = "Here is a String for testing"
        environment.append(other)
        environment.tail = "\n"
        summary = etree.Element('summary')
        summary.attrib['test_plan_name'] = "Empty test_plan_name"
        start_at = etree.Element('start_at')
        start_at.text = start_time
        end_at = etree.Element('end_at')
        end_at.text = end_time
        summary.append(start_at)
        summary.append(end_at)
        summary.tail = "\n  "
        rt.insert(0, summary)
        rt.insert(0, environment)
        
        # add XSL support to testkit-lite
        DECLARATION = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="testresult.xsl"?>\n"""
        with open(mergefile, 'w') as output:
            output.write(DECLARATION)
            ep.write(output, xml_declaration=False, encoding='utf-8')
        
        # change &lt;![CDATA[]]&gt; to <![CDATA[]]>
        self.replace_cdata(mergefile)

        if self.resultfile:
                copyfile(mergefile, self.resultfile)

    def pretty_print(self, ep, resultfile):
        rawstr = etree.tostring(ep.getroot(), 'utf-8')
        t = minidom.parseString(rawstr)
        open(resultfile, 'w+').write(t.toprettyxml(indent="  "))

    def execute_external_test(self, testsuite, exe_sequence):
        """Run external test"""
        import subprocess, thread
        #from  testkithttpd import startup
        from testkithttpd import startup
        if self.bdryrun:
            print "[ WRTLauncher mode does not support dryrun ]"
            return True
        #start http server in here
        try:
            parameters = {}
            parameters.setdefault("pid_log", self.pid_log)
            parameters.setdefault("testsuite", testsuite)
            parameters.setdefault("exe_sequence", exe_sequence)
            parameters.setdefault("client_command", self.external_test)
            if self.fullscreen:
                parameters.setdefault("hidestatus", "1")
            else:
                parameters.setdefault("hidestatus", "0")
            import re
            import ctypes
            http_server_pid = "none"
            fi, fo, fe = os.popen3("netstat -tpa | grep 8000")
            for line in fo.readlines():
                pattern = re.compile('([0-9]*)\/python')
                match = pattern.search(line)
                if match:
                    http_server_pid = match.group(1)
                    try:
                        if platform.system() == "Linux":
                            os.kill(int(http_server_pid), 9)
                            print "[ kill existing http server, pid: %s ]" % http_server_pid
                        else:
                            kernel32 = ctypes.windll.kernel32
                            handle = kernel32.OpenProcess(1, 0, int(http_server_pid))
                            kill_result = kernel32.TerminateProcess(handle, 0)
                            print "[ kill existing http server, pid: %s ]" % http_server_pid
                    except Exception, e:
                        pattern = re.compile('No such process')
                        match = pattern.search(str(e))
                        if not match:
                            print "[ fail to kill existing http server, pid: %s, error: %s ]" % (int(pid), e)
            if http_server_pid == "none":
                print "[ start new http server ]"
            else:
                print "[ start new http server in 3 seconds ]"
                time.sleep(3)
            startup(parameters)

        except Exception, e:
            print e
        return True

    def apply_filter(self, rt):
        def case_check(tc):
            rules = self.filter_rules
            for key in rules.iterkeys():
                if key in ["suite", "set"]:
                    continue
                #Check attribute
                t_val = tc.get(key)
                if t_val:
                    if not t_val in rules[key]:
                        return False
                else:
                    #Check sub-element
                    items = tc.getiterator(key)
                    if items: 
                        t_val = []
                        for i in items:
                            t_val.append(i.text)
                        if len(set(rules[key]) & set(t_val)) == 0:
                            return False
            return True
        
        rules = self.filter_rules
        for tsuite in rt.getiterator('suite'):
            if rules.get('suite'):
                if tsuite.get('name') not in rules['suite']:
                    rt.remove(tsuite)
            for tset in tsuite.getiterator('set'):
                if rules.get('set'):
                    if tset.get('name') not in rules['set']:
                        tsuite.remove(tset)
                       
        for tset in rt.getiterator('set'):
            for tc in tset.getiterator('testcase'):
                if not case_check(tc):
                    tset.remove(tc)
 
    def execute(self, testxmlfile, resultfile):
        def exec_testcase(case):
            ok = True
            rt_code, stdout, stderr = None, None, None

            """ Handle manual test """
            if case.get('execution_type', '') == 'manual':
                case.set('result', 'N/A')
                self.core_manual_flag = 1
                try:
                    for attr in case.attrib:
                        print "    %s: %s" % (attr, case.get(attr))
                    notes = case.find("description/notes")
                    print "    notes: %s" % notes.text
                    descs = case.getiterator("step_desc")
                    for desc in descs:
                        print "    desc: %s" % desc.text
                except:
                    pass
                return ok

            case.set('result', 'BLOCK')
            testentry_elm = case.find('description/test_script_entry')
            expected_result = testentry_elm.get('test_script_expected_result', '0')
            # Construct result info node
            resinfo_elm = etree.Element('result_info')
            res_elm = etree.Element('actual_result')
            start_elm = etree.Element('start')
            end_elm = etree.Element('end')
            stdout_elm = etree.Element('stdout')
            stderr_elm = etree.Element('stderr')
            resinfo_elm.append(res_elm)
            resinfo_elm.append(start_elm)
            resinfo_elm.append(end_elm)
            resinfo_elm.append(stdout_elm)
            resinfo_elm.append(stderr_elm)
            
            case.append(resinfo_elm)

            start_elm.text = datetime.today().strftime("%Y-%m-%d_%H_%M_%S")
            if self.bdryrun:
                return_code, stderr, stdout = "0", "Dryrun error info", "Dryrun output"
            else:
                if testentry_elm.get('timeout'):
                    return_code, stderr, stdout = \
                    shell_exec(testentry_elm.text, "no_log", str2number(testentry_elm.get('timeout')), True)
                else:
                    return_code, stderr, stdout = \
                    shell_exec(testentry_elm.text, "no_log", 90, True)

            # convert all return code to string in order to compare test result
            if return_code is None:
                res_elm.text = 'None'
            else:
                res_elm.text = str(return_code)
            stdout_elm.text = stdout
            stderr_elm.text = stderr

            # record endtime
            end_elm.text = datetime.today().strftime("%Y-%m-%d_%H_%M_%S")

            if return_code is not None:
                if expected_result == res_elm.text:
                    case.set('result', 'PASS')
                else:
                    case.set('result', 'FAIL')

            # Check performance test
            measures = case.getiterator('measurement')
            for m in measures:
                ind = m.get('name')
                fname = m.get('file')
                if fname and _e(fname):
                    try:
                        config = ConfigParser.ConfigParser()
                        config.read(fname)
                        val = config.get(ind, 'value')
                        m.set('value', val)
                    except Exception, e:
                        print e
                    
            return ok

        # Go
        try:
            ep = etree.parse(testxmlfile)
            rt = ep.getroot()
            for tsuite in rt.getiterator('suite'):
                for tcaselog in tsuite.getiterator('testcase'):
                    if tcaselog.get('execution_type') == 'manual':
                        print "[Suite] execute manual suite: %s" % tsuite.get('name')
                        break
                    else:
                        print "[Suite] execute suite: %s" % tsuite.get('name')
                        break
                for tset in tsuite.getiterator('set'):
                    print "[Set] execute set: %s" % tset.get('name')
                    for tc in tset.getiterator('testcase'):
                        print "[Case] execute case: %s" % tc.get("id")
                        exec_testcase(tc)
            ep.write(resultfile)
            return True
        except Exception, e:
            print e
            return False

    def replace_cdata(self, file_name):
        abs_path = mktemp()
        new_file = open(abs_path, 'w')
        old_file = open(file_name)
        for line in old_file:
            line_temp = line.replace('&lt;![CDATA', '<![CDATA')
            new_file.write(line_temp.replace(']]&gt;', ']]>'))
        new_file.close()
        old_file.close()
        remove(file_name)
        move(abs_path, file_name)

