#!/usr/bin/env python

# LSST Data Management System
# Copyright 2014 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
This tests the logging system in a variety of ways.
"""

import lsst.log as log
import os
import shutil
import sys
import tempfile
import unittest

class TestLog(unittest.TestCase):

    class StdoutCapture(object):
        """
        Context manager to redirect stdout to a file.
        """

        def __init__(self, filename):
            self.stdout = None
            self.outputFilename = filename

        def __enter__(self):
            self.stdout = os.dup(1)
            os.close(1)
            os.open(self.outputFilename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)

        def __exit__(self, type, value, traceback):
            if self.stdout is not None:
                os.close(1)
                os.dup(self.stdout)
                os.close(self.stdout)
                self.stdout = None

    def setUp(self):
        """Make a temporary directory and a log file in it."""
        self.tempDir = tempfile.mkdtemp()
        self.outputFilename = os.path.join(self.tempDir, "log.out")
        self.stdout = None

    def tearDown(self):
        """Remove the temporary directory."""
        shutil.rmtree(self.tempDir)

    def configure(self, configuration):
        """
        Create a configuration file in the temporary directory and populate
        it with the provided string.
        """
        log.configure_prop(configuration.format(self.outputFilename))

    def check(self, reference):
        """Compare the log file with the provided reference text."""
        with open(self.outputFilename, 'r') as f:
            lines = [l.split(']')[-1] for l in f.readlines()]
            reflines = [l + "\n" for l in reference.split("\n") if l != ""]
            map(self.assertEqual, lines, reflines)


###############################################################################

    def testDefaultLogger(self):
        """Check the default root logger name."""
        self.assertEqual(log.getDefaultLoggerName(), "")

    def testBasic(self):
        """
        Test basic log output.  Since the default threshold is INFO, the
        TRACE message is not emitted.
        """
        with TestLog.StdoutCapture(self.outputFilename):
            log.configure()
            log.trace("This is TRACE")
            log.info("This is INFO")
            log.debug("This is DEBUG")
            log.warn("This is WARN")
            log.error("This is ERROR")
            log.fatal("This is FATAL")
            log.info("Format %d %g %s", 3, 2.71828, "foo")
        self.check("""
 INFO root null - This is INFO
 DEBUG root null - This is DEBUG
 WARN root null - This is WARN
 ERROR root null - This is ERROR
 FATAL root null - This is FATAL
 INFO root null - Format 3 2.71828 foo
""")

    def testContext(self):
        """Test the log context/component stack."""
        with TestLog.StdoutCapture(self.outputFilename):
            log.configure()
            log.trace("This is TRACE")
            log.info("This is INFO")
            log.debug("This is DEBUG")
            with log.LogContext("component"):
                log.trace("This is TRACE")
                log.info("This is INFO")
                log.debug("This is DEBUG")
            log.trace("This is TRACE 2")
            log.info("This is INFO 2")
            log.debug("This is DEBUG 2")
            with log.LogContext("comp") as ctx:
                log.trace("This is TRACE 3")
                log.info("This is INFO 3")
                log.debug("This is DEBUG 3")
                ctx.setLevel(log.INFO)
                self.assertEqual(ctx.getLevel(), log.INFO)
                self.assert_(ctx.isEnabledFor(log.INFO))
                log.trace("This is TRACE 3a")
                log.info("This is INFO 3a")
                log.debug("This is DEBUG 3a")
                with log.LogContext("subcomp", log.TRACE) as ctx2:
                    self.assertEqual(ctx2.getLevel(), log.TRACE)
                    log.trace("This is TRACE 4")
                    log.info("This is INFO 4")
                    log.debug("This is DEBUG 4")
                log.trace("This is TRACE 5")
                log.info("This is INFO 5")
                log.debug("This is DEBUG 5")

        self.check("""
 INFO root null - This is INFO
 DEBUG root null - This is DEBUG
 INFO component null - This is INFO
 DEBUG component null - This is DEBUG
 INFO root null - This is INFO 2
 DEBUG root null - This is DEBUG 2
 INFO comp null - This is INFO 3
 DEBUG comp null - This is DEBUG 3
 INFO comp null - This is INFO 3a
 TRACE comp.subcomp null - This is TRACE 4
 INFO comp.subcomp null - This is INFO 4
 DEBUG comp.subcomp null - This is DEBUG 4
 INFO comp null - This is INFO 5
""")

    def testPattern(self):
        """
        Test a complex pattern for log messages, including Mapped
        Diagnostic Context (MDC).
        """
        with TestLog.StdoutCapture(self.outputFilename):
            self.configure("""
log4j.rootLogger=DEBUG, CA
log4j.appender.CA=ConsoleAppender
log4j.appender.CA.layout=PatternLayout
log4j.appender.CA.layout.ConversionPattern=%-5p %c %C %M (%F:%L) %l - %m - %X%n
""")
            log.trace("This is TRACE")
            log.info("This is INFO")
            log.debug("This is DEBUG")

            log.MDC("x", 3)
            log.MDC("y", "foo")
            log.MDC("z", TestLog)

            log.trace("This is TRACE 2")
            log.info("This is INFO 2")
            log.debug("This is DEBUG 2")
            log.MDCRemove("z")

            with log.LogContext("component"):
                log.trace("This is TRACE 3")
                log.info("This is INFO 3")
                log.debug("This is DEBUG 3")
                log.MDCRemove("x")
                log.trace("This is TRACE 4")
                log.info("This is INFO 4")
                log.debug("This is DEBUG 4")

            log.trace("This is TRACE 5")
            log.info("This is INFO 5")
            log.debug("This is DEBUG 5")

            log.MDCRemove("y")

        # Use format to make line numbers easier to change.
        self.check("""
INFO  root  testPattern (logTest.py:{0[0]}) logTest.py({0[0]}) - This is INFO - {{}}
DEBUG root  testPattern (logTest.py:{0[1]}) logTest.py({0[1]}) - This is DEBUG - {{}}
INFO  root  testPattern (logTest.py:{0[2]}) logTest.py({0[2]}) - This is INFO 2 - {{{{x,3}}{{y,foo}}{{z,<class '__main__.TestLog'>}}}}
DEBUG root  testPattern (logTest.py:{0[3]}) logTest.py({0[3]}) - This is DEBUG 2 - {{{{x,3}}{{y,foo}}{{z,<class '__main__.TestLog'>}}}}
INFO  component  testPattern (logTest.py:{0[4]}) logTest.py({0[4]}) - This is INFO 3 - {{{{x,3}}{{y,foo}}}}
DEBUG component  testPattern (logTest.py:{0[5]}) logTest.py({0[5]}) - This is DEBUG 3 - {{{{x,3}}{{y,foo}}}}
INFO  component  testPattern (logTest.py:{0[6]}) logTest.py({0[6]}) - This is INFO 4 - {{{{y,foo}}}}
DEBUG component  testPattern (logTest.py:{0[7]}) logTest.py({0[7]}) - This is DEBUG 4 - {{{{y,foo}}}}
INFO  root  testPattern (logTest.py:{0[8]}) logTest.py({0[8]}) - This is INFO 5 - {{{{y,foo}}}}
DEBUG root  testPattern (logTest.py:{0[9]}) logTest.py({0[9]}) - This is DEBUG 5 - {{{{y,foo}}}}
""".format([x + 173 for x in (0, 1, 8, 9, 14, 15, 18, 19, 22, 23)]))

    def testFileAppender(self):
        """Test configuring logging to go to a file."""
        self.configure("""
log4j.rootLogger=DEBUG, FA
log4j.appender.FA=FileAppender
log4j.appender.FA.file={0}
log4j.appender.FA.layout=SimpleLayout
""")
        log.MDC("x", 3)
        with log.LogContext("component"):
            log.trace("This is TRACE")
            log.info("This is INFO")
            log.debug("This is DEBUG")
        log.MDCRemove("x")

        self.check("""
INFO - This is INFO
DEBUG - This is DEBUG
""")

    def testPythonLogging(self):
        """Test logging through the Python logging interface."""
        with TestLog.StdoutCapture(self.outputFilename):
            import logging
            lgr = logging.getLogger()
            lgr.setLevel(logging.INFO)
            lgr.addHandler(log.LogHandler())
            log.configure()
            lgr.info("This is INFO")
            logging.shutdown()

        self.check("""
 INFO root null - This is INFO
""")

    def testLogger(self):
        """
        Test log object.
        """
        with TestLog.StdoutCapture(self.outputFilename):
            log.configure()
            logger = log.Logger("b")
            logger.trace("This is TRACE")
            logger.info("This is INFO")
            logger.debug("This is DEBUG")
            logger.warn("This is WARN")
            logger.error("This is ERROR")
            logger.fatal("This is FATAL")
            logger.info("Format %d %g %s", 3, 2.71828, "foo")
        self.check("""
 INFO b null - This is INFO
 DEBUG b null - This is DEBUG
 WARN b null - This is WARN
 ERROR b null - This is ERROR
 FATAL b null - This is FATAL
 INFO b null - Format 3 2.71828 foo
""")


####################################################################################
def main():
    unittest.main()

if __name__ == "__main__":
    main()
