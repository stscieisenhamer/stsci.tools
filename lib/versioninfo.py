#   Program:    versionInfo.py
#   Author:     Christopher Hanley
#   Date:       19 January 2004
#   Purpose:
#       To print a user's system information when providing user support.
#
#   Version:
#       Version 0.1.0, 19-Jan-04: Program created. -- CJH
#       Version 0.1.1, 20-Jan-04: Modified program to
#                                 loop over a taskList object. -- CJH
#
#

__version__ = '0.1.1'

def printVersionInfo():
    # Print the current path information
    try:
        print "Path information:"
        print "-----------------"
        import sys
        print sys.path
        print " "
    except:
        print "Unable to get sys information."
        print " "

    # Define the list of tasks to test
    taskList = [
                'numarray',
                'Numeric',
                'pyfits',
                'pyraf',
                'multidrizzle',
                'pydrizzle',
                'upincd',
                'deriv',
                'quickDeriv'
                ]

    # Test the list of software tasks
    for software in taskList:
        print software+":"
        print "-----------"
        try:
            package = __import__(software)
            try:
                print "version -> ",package.__version__
            except:
                print "__version__ attribute is not defined"
            try:
                pathName = package.__path__
            except:
                pathName = package.__file__
            print "location -> ",pathName
        except:
            print software+" not found in path..."
        print " "

    # Print instruction message.
    print "PLEASE PASTE THE OUTPUT FROM THIS TASK "
    print "INTO AN E-MAIL MESSAGE AND SEND IT WITH"
    print "YOUR PROBLEM DESCRIPTION TO SSB!"
    print " "
    print "SUPPORT ADDRESS: help@stsci.edu "

if __name__ == '__main__':
    printVersionInfo()