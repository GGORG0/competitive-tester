#!/usr/bin/env python3

"""
Program tester

It can test C++ programs or precompiled binaries.
It can use:
- .in/.out files as tests
- .in/.py files as tests
    the .py file should contain a function called test that takes the output as a parameter and returns True if the test passed
- .in/ALLTESTS.py files as tests
    the ALLTESTS.py file should contain a function called test that takes the input and output as a parameter and returns True if the test passed
- TESTS.json files as all tests
    the TESTS.json file should contain a dictionary with the test name as the key and a list with the input and output as the value
- TESTS.json/ALLTESTS.py files as all tests
    - the ALLTESTS.py file should contain a function called test that takes the input and output as a parameter and returns True if the test passed
    - TESTS.json should contain a dictionary with the test name as the key and the input as the value

Usage:
python3 test.py --test-dir <test directory> <program>
or
python3 test.py --auto <program> (it will search for the tests in the same directory as the program)
"""

# TODO: Add support for GENERATOR.py files
# TODO: Add support for a separate brute force program for checking the output
# TODO: Add support for uploading programs to Themis

import subprocess
import argparse
import os
import sys
import glob
import importlib
import json
import time
import colorama

ok_icon = colorama.Fore.GREEN + '✓'
fail_icon = colorama.Fore.RED + '✗'


def print_colored(color, text):
    print(color + text + colorama.Fore.RESET)


def print_error(text, exit_program=True, prefix=True, icon=True):
    print(f'{colorama.Fore.RED}{fail_icon + " " if icon else ""}{"ERROR: " if prefix else ""}{text}{colorama.Fore.RESET}')
    if exit_program:
        sys.exit(1)


def print_success(text):
    print(f'{colorama.Fore.GREEN}{ok_icon} {text}{colorama.Fore.RESET}')


def print_inprogress(text):
    print(f'{colorama.Fore.YELLOW}{text}{colorama.Fore.RESET}', end=' ')


def print_info(text):
    print(f'{colorama.Fore.CYAN}{text}{colorama.Fore.RESET}')


def better_dirname(p):
    return os.path.dirname(p) if os.path.dirname(p) else '.'


def init():
    colorama.init()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--test-dir',
        help='The directory containing the tests.')
    parser.add_argument(
        '--auto',
        help='Automatically search for tests in the same directory as the program.',
        action='store_true')
    parser.add_argument(
        'program',
        help='The program to test. Can be an executable or a C++ file (no extension or .cpp).')
    args = parser.parse_args()

    # Check if the provided file exists
    if not os.path.isfile(args.program):
        print_error(f'File does not exist: {args.program}')

    # Check if either --test-dir or --auto is provided
    if not args.test_dir and not args.auto:
        print_info('Enabling --auto mode.')
        args.auto = True

    # Check if both --test-dir and --auto are provided
    if args.test_dir and args.auto:
        print_error('Only one of --test-dir or --auto must be provided.')

    # Check if the provided test directory exists
    if args.test_dir and not os.path.isdir(args.test_dir):
        print_error(f'Directory does not exist: {args.test_dir}')

    # Set the test directory to the same directory as the program if --auto is provided
    if args.auto:
        if os.path.isdir(os.path.join(better_dirname(args.program), 'tests')):
            args.test_dir = os.path.join(
                better_dirname(args.program), 'tests')
        elif os.path.isdir(better_dirname(args.program)):
            args.test_dir = better_dirname(args.program)
        else:
            print_error(
                f'Could not find tests in the same directory as {args.program} (try --test-dir manually).')

    # Add the test directory to the path
    sys.path.insert(0, args.test_dir)

    return args


def compile_cpp(program):
    # Compile the program
    print_inprogress(f'Compiling {program}...')
    subprocess.run(['g++', '-o', program[:-4], program], check=True)
    print_success('Done!')


def get_tests(test_dir):
    # Import ALLTESTS.py if it exists
    alltests = None
    if os.path.isfile(os.path.join(test_dir, 'ALLTESTS.py')):
        alltests = importlib.import_module('ALLTESTS').test

    # { name: (type, input, output) } where type is 'static' or 'checker'
    tests = {}

    # Get .in files
    for x in glob.glob(os.path.join(test_dir, '*.in')):
        name = os.path.basename(x)[:-3]

        # Read the input
        with open(x, 'r') as f:
            test_input = f.read()

        if os.path.isfile(x[:-3] + '.out'):
            # We have a static .in/.out test
            # Read the output
            with open(x[:-3] + '.out', 'r') as f:
                test_output = f.read()

            tests[name + '#in/out'] = ('static', test_input, test_output)
        if os.path.isfile(x[:-3] + '.py'):
            # We have a checker .in/.py test
            # Import the checker
            checker = importlib.import_module(name).test

            tests[name + '#in/py'] = ('checker', test_input, checker)
        if alltests is not None:
            # We have a checker ALLTESTS.py test

            tests[name + '#in/atpy'] = ('checker', test_input, alltests)

    # Get TESTS.json tests
    if os.path.isfile(os.path.join(test_dir, 'TESTS.json')):
        with open(os.path.join(test_dir, 'TESTS.json'), 'r') as f:
            file = json.load(f)

        # key is the test name, value is an array with the input and optional output
        for name, test in file.items():
            if len(test) == 1:
                # We have a checker TESTS.json test
                tests[name + '#json/atpy'] = ('checker', test[0], alltests)
            elif len(test) == 2:
                # We have a static TESTS.json test
                tests[name + '#json'] = ('static', test[0], test[1])

    return tests


def run_tests(program, tests):
    passed_tests = 0
    for name, test in tests.items():
        test_type, test_input, test_output = test
        print_inprogress(f'Running {test_type} test {name}...')

        try:
            start_time = time.time()
            proc = subprocess.run(
                [program],
                input=test_input,
                encoding='utf-8',
                stdout=subprocess.PIPE,
                check=True)
            end_time = time.time()
            run_time = end_time - start_time
            actual_output = proc.stdout.strip()

            if test_type == 'static':
                if actual_output == test_output.strip():
                    print_success(f'Passed ({run_time:.3f}s)!')
                    passed_tests += 1
                else:
                    print_error(f'Failed ({run_time:.3f}s)!', False, False)
                    if len(test_output) > 100 or len(actual_output) > 100:
                        print_error(' (Output too long to print.)',
                                    False, False, False)
                    else:
                        print_error(' Expected output:', False, False, False)
                        print_error(test_output, False, False, False)
                        print_error(' Actual output:', False, False, False)
                        print_error(actual_output, False, False, False)
            elif test_type == 'checker':
                if test_output(test_input, actual_output):
                    print_success(f'Passed ({run_time:.3f}s)!')
                    passed_tests += 1
                else:
                    print_error(f'Failed ({run_time:.3f}s)!', False, False)
                    if len(actual_output) > 100:
                        print_error(' (Output too long to print.)',
                                    False, False, False)
                    else:
                        print_error(' Output:', False, False, False)
                        print_error(actual_output, False, False, False)
        except subprocess.CalledProcessError as err:
            print_error('Failed!', False, False)
            print_error(
                f' Program exited with non-zero exit code {err.returncode}.', False, False)
            if len(err.stdout) > 100:
                print_error(' (Output too long to print.)',
                            False, False, False)
            else:
                print_error(' Output:', False, False, False)
                print_error(' ' + err.stdout, False, False, False)

    return passed_tests


def main():
    args = init()

    # Compile the program if it's a C++ file
    if args.program.endswith('.cpp'):
        compile_cpp(args.program)
        args.program = args.program[:-4]
        print()

    tests = get_tests(args.test_dir)
    passed = run_tests(args.program, tests)
    print()

    if passed == len(tests):
        print_success('All tests passed!')
    else:
        print_error(
            f'Passed {passed} out of {len(tests)} tests ({round(passed/len(tests)*100)}%).',
            False, False)


if __name__ == '__main__':
    main()
