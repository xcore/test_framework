import logging
import os

""" An abstraction layer on top of the default logging library such that
    errors and warnings can be automatically prefixed but debug and info
    messages are not.

    It also tracks error/warning counts and provides a standard configuration
    and reporting function.
"""

counts = {
    'errors': 0,
    'warnings' : 0
}

indent_step = '    '
indent = ''

def log_indent():
    global indent
    indent += indent_step

def log_unindent():
    global indent
    assert len(indent) >= len(indent_step)
    indent = indent[len(indent_step):]

def log_error(message, exc_info=False):
    logging.error('%sERROR: %s' % (indent, message), exc_info=exc_info)
    counts['errors'] += 1

def log_warning(message):
    logging.warning('%sWARNING: %s' % (indent, message))
    counts['warnings'] += 1

def log_info(message):
    logging.info('%s%s' % (indent, message))

def log_debug(message):
    logging.debug('%s%s' % (indent, message))

def configure_logging(level_console='INFO', level_file=None, filename='run.log', summary_filename=None):
    if level_file:
        logging.basicConfig(level=eval('logging.%s' % level_file), format='%(message)s',
                filename=os.path.join(os.getcwd(), filename), filemode='w')
        console = logging.StreamHandler()
        console.setLevel(eval('logging.%s' % level_console))
        formatter = logging.Formatter('%(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)
        if summary_filename:
            summary = logging.FileHandler(summary_filename, mode='w')
            summary.setLevel(eval('logging.%s' % level_console))
            summary.setFormatter(formatter)
            logging.getLogger('').addHandler(summary)
    else:
        logging.basicConfig(level=eval('logging.%s' % level_console), format='%(message)s')

def print_status_summary():
    if counts['errors'] or counts['warnings']:
        print '%d ERROR%s and %d WARNING%s detected' % (
            counts['errors'], ('' if counts['errors'] == 1 else 'S'),
            counts['warnings'], ('' if counts['warnings'] == 1 else 'S'))
    else:
      print "Test passed"

