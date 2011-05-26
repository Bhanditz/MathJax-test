# -*- Mode: Python; tab-width: 2; indent-tabs-mode:nil; -*-
# vim: set ts=2 et sw=2 tw=80:
# ***** BEGIN LICENSE BLOCK *****
# Version: Apache License 2.0
#
# Copyright (c) 2011 Design Science, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributor(s):
#   Frederic Wang <fred.wang@free.fr> (original author)
#
# ***** END LICENSE BLOCK *****

"""
@package runTestsuite
This module is the main script of the test launcher.
"""

from datetime import datetime, timedelta
import ConfigParser
import argparse
import errno
import gzip
import math
import os
import platform
import re
import reftest
import seleniumMathJax
import string
import subprocess
import sys
import time
import unittest

def getOperatingSystem(aOperatingSystem):

    """
    @fn getOperatingSystem(aOperatingSystem)
    @brief get the operating system

    @param aOperatingSystem the name of an operating system or "auto"
    @return the name of the operating system

    @details The result used is the operating system if it specified or the
    value of Python's platform.system()
    """

    if aOperatingSystem != "auto":
        return aOperatingSystem

    return platform.system()

def getBrowserStartCommand(aBrowserPath, aOS, aBrowser):

    """
    @fn getBrowserStartCommand(aBrowserPath, aOS, aBrowser)
    @brief get the browser start command

    @param aBrowserPath the path to the executable of the browser or "auto"
    @param aOS the name of the operating system
    @param aBrowser the name of the browser
    @return the start command to be used by Selenium 

    @details The return value is "*firefox", "*googlechrome", "*opera",
    "*iexploreproxy", "*konqueror /usr/bin/konqueror" or "unknown" if the brower
    was not recognized.
    """

    if aBrowser == "Firefox":
        startCommand = "*firefox"
    elif (aOS == "Windows" or aOS == "Mac") and aBrowser == "Safari":
        startCommand = "*safariproxy"
    elif aBrowser == "Chrome":
        startCommand = "*googlechrome"
    elif aBrowser == "Opera":
        startCommand = "*opera"
    elif aOS == "Windows" and aBrowser == "MSIE":
        startCommand = "*iexploreproxy"
    elif aOS == "Linux" and aBrowser == "Konqueror":
        startCommand = "*konqueror"
    else:
        startCommand = "*custom"
    
    if aBrowserPath == "auto":
        if startCommand == "*custom":
            print >> sys.stderr, "Unknown browser"
            return "unknown"

        if aOS == "Linux" and aBrowser == "Konqueror":
           startCommand = startCommand + " /usr/bin/konqueror" 
    else:
        startCommand = startCommand + " " + aBrowserPath
    
    return startCommand

def getOutputFileName(aDirectory, aSelenium):

    """
    @fn getOutputFileName(aDirectory, aSelenium)
    @brief build a file name for the output

    @param aDirectory directory where the test output will be stored
    @param aSelenium @ref seleniumMathJax object

    @return Concatenation of aDirectory, the operating system, the browser,
    the browser mode and the font, separated by underscores.
    """

    return \
        aDirectory + \
        aSelenium.mOperatingSystem + "_" + \
        aSelenium.mBrowser + "_" + \
        aSelenium.mBrowserMode + "_" + \
        aSelenium.mFont

def boolToString(aBoolean):
    """
    @fn boolToString(aBoolean)
    @brief A simple function to convert a boolean to a string

    @return the string "true" or "false"
    """
    if aBoolean:
        return "true"
    return "false"

def gzipFile(aFile):
    """
    @fn gzipFile(aFile)
    @brief Compress a file using the gzip format.

    @param aFile the file to compress

    @details The action is the same as the gzip command: aFile is compressed
    into an archive aFile.gz and the original file is removed.
    """
    f_in = open(aFile, "rb")
    f_out = gzip.open(aFile + ".gz", "wb")
    f_out.writelines(f_in)
    f_out.close()
    f_in.close()
    os.remove(aFile)

def printReftestList():
    """
    @fn printReftestList()
    @brief generate the file web/reftestList.js
    """
    suite = reftest.reftestSuite(True, True, None)
    fp = file("web/reftestList.js", "wb")
    stdout = sys.stdout
    sys.stdout = fp
    print "// This file is automatically generated. Do not edit."
    print "/**"
    print " * @file"
    print " * A file generated by runTestsuite.py to represent the test suite"
    print " *" 
    print " * @var Array gTestSuite"
    print " * An array representing the file hierarchy of the test suite"
    print " */"
    print "var gTestSuite = [\"/MathJax-test/\"",
    suite.addReftests(None, "reftest.list", -1)
    print "]"
    sys.stdout = stdout
    fp.close()

if __name__ == "__main__":

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="A Python script to run MathJax automated tests.")
    parser.add_argument("-c", "--config", nargs = "?", default = "default.cfg",
                        help="A comma separated list of files describing the \
parameters of the automated test instance to run. The default configuration \
file is default.cfg.")
    parser.add_argument("-o", "--output", nargs = "?", default = None,
                        help="By default, the output files are stored in \
default results/YEAR-MONTH-DAY/TIME/. This option allows to specify a \
custom sub directory instead of TIME/. The name of this directory can only \
contain alphanumeric characters and its length must not exceed ten characters.")
    parser.add_argument("-p", "--printList", nargs = "?",
                        default = argparse.SUPPRESS,
                        help="Print the list of all the tests in a file \
reftestList.txt")
    args = parser.parse_args()

    # if the option --printList is passed, only generate the file
    # reftestList.txt
    if hasattr(args, "printList"):
        print "Generating reftestList.js...",
        printReftestList()
        print "done"
        exit(0)

    # create the date directory
    now = datetime.utcnow();
    directory = "results/" + now.strftime("%Y-%m-%d") + "/"
    if not os.path.exists(directory):
        os.makedirs(directory)

    # create the subdirectory
    if args.output and re.match("^([0-9]|[a-z]|[A-Z]){1,10}$", args.output):
        directory += args.output + "/"
    else:
        directory += now.strftime("%H-%M-%S/")

    if not os.path.exists(directory):
        os.makedirs(directory)

    # execute testing instances for all the config files
    configFileList = args.config.split(",")

    for configFile in configFileList:

        if (not os.path.isfile(configFile)):
            print >> sys.stderr,\
                "Warning: config file " + configFile + " not found!"
            continue

        # Load configuration file
        config = ConfigParser.ConfigParser()
        config.readfp(open(configFile))

        # framework section
        section = "framework"
        host = config.get(section, "host")
        port = config.getint(section, "port")
        mathJaxPath = config.get(section, "mathJaxPath")
        mathJaxTestPath = config.get(section, "mathJaxTestPath")
        timeOut = config.getint(section, "timeOut")
        fullScreenMode = config.getboolean(section, "fullScreenMode")
        formatOutput = config.getboolean(section, "formatOutput")
        compressOutput = config.getboolean(section, "compressOutput")
    
        # platform section
        section = "platform"
        operatingSystem = getOperatingSystem(config.get(section,
                                                        "operatingSystem"))
        browserList = config.get(section, "browser").split()
        browserModeList = config.get(section, "browserMode").split()
        browserPath = config.get(section, "browserPath")
        fontList = config.get(section, "font").split()
        nativeMathML = config.getboolean(section, "nativeMathML")
    
        # testsuite section
        section = "testsuite"
        runSlowTests = config.getboolean(section, "runSlowTests")
        runSkipTests = config.getboolean(section, "runSkipTests")
        listOfTests = config.get(section, "listOfTests")
       
        if ((len(browserList) > 1 or len(browserModeList) or len(fontList) > 1)
            and browserPath != "auto"):
            print >> sys.stderr, "Warning: browserPath ignored"
            browserPath = "auto"

        for browser in browserList:
            for font in fontList:
                for browserMode in browserModeList:

                    # Browser mode is only relevant for MSIE
                    if not(browser == "MSIE"):
                        browserMode = "StandardMode"

                    browserStartCommand = getBrowserStartCommand(
                        browserPath,
                        operatingSystem,
                        browser)

                    if browserStartCommand != "unknown":

                        # Create a Selenium instance
                        selenium = seleniumMathJax.seleniumMathJax(
                            host, port, mathJaxPath, mathJaxTestPath,
                            operatingSystem,
                            browser,
                            browserMode,
                            browserStartCommand, 
                            font,
                            nativeMathML,
                            timeOut,
                            fullScreenMode)
                        
                        # Create the test suite
                        suite = reftest.reftestSuite(runSlowTests,
                                                     runSkipTests,
                                                     listOfTests)
                        if listOfTests == "all":
                            index = -1 # all tests
                        else:
                            index = 0 # tests indicated in listOfTests

                        suite.addReftests(selenium, "reftest.list", index)
                        
                        # Create the output file
                        output = getOutputFileName(directory, selenium)
                        outputTxt = output + ".txt"
                        outputHTML= output + ".html"
                        fp = file(outputTxt, "wb")
                        stdout = sys.stdout
                        sys.stdout = fp
                        
                        # Run the test suite
                        startTime = datetime.utcnow()
                        suite.printInfo("Starting Testing Instance ; " +
                                        startTime.isoformat())
                        interrupted = False
                        try:
                            selenium.start()
                            suite.printInfo("host=" + str(host))
                            suite.printInfo("port=" + str(port))
                            suite.printInfo("mathJaxPath = " + mathJaxPath)
                            suite.printInfo("mathJaxTestPath = " +
                                            mathJaxTestPath)
                            suite.printInfo("operatingSystem = " +
                                            operatingSystem)
                            suite.printInfo("browser = " + browser)
                            suite.printInfo("browserMode = " + browserMode)
                            suite.printInfo("font = " + font)
                            suite.printInfo("nativeMathML = " +
                                            boolToString(nativeMathML))
                            suite.printInfo("runSlowTests = " +
                                            boolToString(runSlowTests))
                            unittest.TextTestRunner(sys.stderr,
                                                    verbosity=2).run(suite)
                            selenium.stop()
                            time.sleep(4)
                        except KeyboardInterrupt:
                            selenium.stop()
                            interrupted = True
                            
                        endTime = datetime.utcnow()
                        deltaTime = endTime - startTime
                        if not interrupted:
                            suite. printInfo("Testing Instance Finished ; " +
                                             endTime.isoformat())
                        else:
                            suite.printInfo("Testing Instance Interrupted ; " +
                                            endTime.isoformat())

                        suite.printInfo("Testing Instance took " +
                                        str(math.trunc
                                            (deltaTime.total_seconds() / 60)) +
                                        " minute(s) and " +
                                        str(deltaTime.seconds % 60) +
                                        " second(s)")
                        sys.stdout = stdout
                        fp.close()

                        if not interrupted:
                            if formatOutput:
                                # Execute the Perl script to format the output
                                print "Formatting the text ouput...",
                                pipe = subprocess.Popen(
                                    ["perl", "clean-reftest-output.pl",
                                     outputTxt],
                                    stdout=subprocess.PIPE)
                                fp = file(outputHTML, "wb")
                                print >> fp, pipe.stdout.read()
                                fp.close()
                                print "done"

                            if compressOutput:
                                # gzip the outputs
                                print "Compressing the output files...",
                                gzipFile(outputTxt)
                                if formatOutput:
                                    gzipFile(outputHTML)
                                print "done"
                        else:
                            print
                            print "Test Launcher received SIGINT!"
                            print "Testing Instance Interrupted."

                    # end if browserStartCommand
                # end browserMode
            # end for font
        # end browser

    exit(0)
