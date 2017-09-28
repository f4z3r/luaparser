#!/usr/bin/env python3
'''
This script parses the lua programming language. It is used to check for
potential errors in the source code (only context free errors).

    Usage:
        python3 Luaparser.py <filename>

        or

        Luaparser.py <filename>

        if PATH is correctly configured.

    Note this script can also be used as a module for another program to
    recover the parse(<filename>) function or any other indiviual function
    declared in this code.

    Author: 1407176
'''
import sys
import shlex
import re


# Precompile BREs for later use in pattern recognition
name = re.compile('[_A-Za-z][_A-Za-z0-9]*')
number = re.compile('-?[0-9]+(\.[0-9]+)?')
string = re.compile('(\"(\\.|[^\"])*\")|(\'(\\.|[^\'])*\')')
keyword = re.compile('and|break|do|else|elseif|end|false|for|function|if|'+
                     'in|local|nil|not|or|repeat|return|then|true|until|while')
unop = re.compile('-|not|#')
binop_1 = re.compile('\+|-|\*|/|\^|%|and|or')
binop_2 = re.compile('>=|<=|==|~=|\.\.')
binop_3 = re.compile('<|>')
fieldsep = re.compile(',|;')

# Temporary line list for improved lexer. This will be used as temporary
# storage for each lexed line of input
_line_list = []

# Storage list for declared functions and global variables used to temporarily
# store head positions
function_list = []
_function_temp_beg = []
_function_temp_end = []
_named_function = False

# Storage list for errors found by the parser
error_list = []

# Storage list for all tokens from the input stream and head position
# indicators
token_list = []
_cl = 0
_ct = 0


def parse(filename):
    '''
    Reads an input file and parses the stream for errors according to the lua
    programming language.
        Arguments:
            <filename>  :   file to be parsed

        Output:
            Prints messages about syntax errors to the console / terminal.
    '''

    # Read source file to line_list and close the file to minimize errors.
    # This also catches any errors if the file is not found or another I/O
    # related error occurs.
    try:
        with open(filename, 'rt') as input_file:
            for _line in input_file:
                _line_list.append(_line)
        input_file.close()
    except IOError:
        print("File not found.")
        sys.exit(1)

    # Reads input and creates a token list. Each line is a list within the
    # token list and two symbols are added to indicate the start and the
    # end of the token stream.
    token_list.append(['___start___'])
    for _line in _line_list:
        _temp_token_list = []
        lexer = shlex.shlex(_line)
        lexer.commenters = ''
        for _token in lexer:
            _temp_token_list.append(_token)
        if _temp_token_list:
            token_list.append(_temp_token_list)
        else:
            token_list.append([''])
    token_list.append(['___eof___'])

    # Reset curent line and curent token indeces
    global _cl, _ct
    _cl = 0
    _ct = 0

    # Parse as long as the eof symbol is not reached and skip over completely
    # invalid statements.
    while True:
        parse_chunk()
        if get_next_token() == '___eof___':
            break
        error("Invalid statement.")
        next_statement()

    # Print the errors (or "No errors found." if none are found)
    print_errors(filename)

    # Print the list of declared functions if no errors have been recorded.
    if len(error_list) == 0:
        print_functions()



##############################################################################
# Individual parse functions

def parse_block():
    '''
    Parses the production:
            <block> -> <chunk>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    return parse_chunk()

def parse_chunk():
    '''
    Parses the production:
            <chunk> -> {<stat> [;]} [<laststat> [;]]

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    while parse_stat():
        if match(';'):
            pass
        else:
            red_position()
    if parse_laststat():
        if match(';'):
            pass
        else:
            red_position()
    return True

def parse_stat():
    '''
    Parses the production:
            <stat> -> <varlist> = <explist>
                    | <functioncall>
                    | do <block> end
                    | while <exp> do <block> end
                    | repeat <block> until <exp>
                    | if <exp> then <block> {elseif <exp> then <block>}
                        [else <block>] end
                    | for <name> = <exp> , <exp> [, <exp>] do <block> end
                    | for <namelist> in <explist> do <block> end
                    | function <funcname> <funcbody>
                    | local function <name> <funcbody>
                    | local <namelist> [= <explist>]

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    global _function_temp_beg, _named_function
    _save = position_get()
    if parse_varlist() and match('='):
        skip_and_test("Invalid expression list.", parse_explist,
                      last_stat=True)
        return True

    elif position_set(_save) and parse_functioncall():
        return True

    elif position_set(_save) and match('do') and parse_block():
        skip_and_test("Invalid statement. Keyword 'end' expected.", match,
                      'end')
        return True

    elif position_set(_save) and match('while'):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Invalid statement. Keyword 'do' expected.", match,
                      'do')
        parse_block()
        skip_and_test("Invalid statement. Keyword 'end' expected.", match,
                      'end')
        return True

    elif position_set(_save) and match('repeat') and parse_block():
        skip_and_test("Invalid statement. Keyword 'until' expected.", match,
                      'until')
        skip_and_test("Invalid expression.", parse_exp, last_stat=True)
        return True

    elif position_set(_save) and match('if'):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Invalid statement. Keyword 'then' expected.", match,
                      'then')
        parse_block()
        _save00 = position_get()

        while True:
            if match('elseif'):
                skip_and_test("Invalid expression.", parse_exp)
                skip_and_test("Invalid statement. Keyword 'then' expected.",
                              match, 'then')
            elif (position_set(_save00) and (not inc_position()) and
                  parse_exp() and match('then')):
                _temp = position_get()
                position_set(_save00)
                inc_position()
                error("Keyword 'elseif' expected.")
                position_set(_temp)
            else:
                break
            parse_block()
            _save00 = position_get()

        if position_set(_save00) and match('else') and parse_block():
            pass
        else:
            red_position()

        skip_and_test("Invalid statement. Keyword 'end' expected.", match,
                      'end')
        return True

    elif position_set(_save) and match('for'):
        if parse_name() and match('='):
            skip_and_test("Invalid expression.", parse_exp)
            skip_and_test("Missing comma after expression.", match, ',')
            skip_and_test("Invalid expression.", parse_exp)
            if match(','):
                skip_and_test("Invalid expression.", parse_exp)
            else:
                red_position()

            skip_and_test("Invalid statement. Keyword 'do' expected.", match,
                          'do')
            parse_block()
            skip_and_test("Invalid statement. Keyword 'end' expected.", match,
                          'end')
            return True

        elif parse_namelist():
            skip_and_test("Invalid statement. Keyword 'in' expected.", match,
                          'in')
            skip_and_test("Invalid expression list.", parse_explist)
            skip_and_test("Invalid statement. Keyword 'do' expected.", match,
                          'do')
            parse_block()
            skip_and_test("Invalid statement. Keyword 'end' expected", match,
                          'end')
            return True

        else:
            position_set(_save)
            return False

    elif position_set(_save) and match('function') and parse_funcname():
        _named_function = True
        if parse_funcbody():

            _function_temp_beg = _save
            save_function()

            return True
        else:
            position_set(_save)
            return False

    elif position_set(_save) and match('local'):
        _save00 = position_get()
        if match('function') and parse_name():
            _named_function = True
            if parse_funcbody():

                _function_temp_beg = _save00
                save_function()

                return True
        elif position_set(_save00) and parse_namelist():
            if match('='):
                skip_and_test("Invalid expression list.", parse_explist)
            else:
                red_position()
            return True
        else:
            position_set(_save)
            return False

    else:
        position_set(_save)
        return False

def parse_laststat():
    '''
    Parses the production:
            <laststat> -> return [<explist>]
                        | break

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('return'):
        if parse_explist():
            pass
        return True
    elif position_set(_save) and match('break'):
        return True
    else:
        position_set(_save)
        return False

def parse_field():
    '''
    Parses the production:
            <field> -> '[' <exp> ']'  = <exp>
                     | <name> = <exp>
                     | <exp>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('\['):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Closing braket expected.", match, '\]')
        skip_and_test("Invalid statement. Equal sign expected.", match, '=')
        skip_and_test("Invalid expression.", parse_exp)
        return True
    elif position_set(_save) and parse_name() and match('='):
        skip_and_test("Invalid expression.", parse_exp)
        return True
    elif position_set(_save) and parse_exp():
        return True
    else:
        position_set(_save)
        return False

def parse_fieldlist():
    '''
    Parses the production:
            <fieldlist> -> <field> {<fieldsep> <field>} [<fieldsep>]

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_field():
        while parse_fieldsep() and parse_field():
            pass
        return True
    else:
        position_set(_save)
        return False

def parse_tableconstructor():
    '''
    Parses the production:
            <tableconstructor> -> '{' [fieldlist] '}'

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('\{'):
        if parse_fieldlist():
            skip_and_test("Closing curly brace expected.", match, '\}')
            return True
        elif match('\}'):
            return True
    else:
        position_set(_save)
        return False

def parse_functioncall():
    '''
    Parses the production:
            <functioncall> -> <name> <prefixexp_bis> <args> <functioncall_bis>
                            | ( <exp> ) <prefixexp_bis> <args> <functioncall_bis>
                            | <name> <prefixexp_bis> : <name> <args> <functioncall_bis>
                            | ( <exp> ) <prefixexp_bis> : <name> <args> <functioncall_bis>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_name() and parse_prefixexp_bis():
        if match(':') and parse_name():
            pass
        else:
            red_position()

        if parse_args():
            pass
        else:
            position_set(_save)
            return False

        parse_functioncall_bis()
        return True
    elif position_set(_save) and match('\('):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Closing parenthesis expected.", match, '\)')
        parse_prefixexp_bis()
        if parse_args():
            pass
        if match(':') and parse_name():
            pass
        else:
            position_set(_save)
            return False

        parse_functioncall_bis()
        return True
    else:
        position_set(_save)
        return False

def parse_functioncall_bis():
    '''
    Parses the production:
            <functioncall_bis> -> <prefixexp_bis> <args> <functioncall_bis>
                                | <prefixexp_bis> : <name> <args> <functioncall_bis>
                                | None

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    parse_prefixexp_bis()

    if parse_args():
        pass
    elif match(':') and parse_name() and parse_args():
        pass
    else:
        position_set(_save)
        return True

    parse_functioncall_bis()
    return True

def parse_prefixexp():
    '''
    Parses the production:
            <prefixexp> -> <name> <prefixexp_bis>
                         | <functioncall> <prefixexp_bis>
                         | ( <exp> ) <prefixexp_bis>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_functioncall():
        parse_prefixexp_bis()
    elif position_set(_save) and parse_name():
        parse_prefixexp_bis()
    elif position_set(_save) and match('\('):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Closing parenthesis expected.", match, '\)')
        parse_prefixexp_bis()
    else:
        position_set(_save)
        return False

    return True

def parse_prefixexp_bis():
    '''
    Parses the production:
            <prefixexp_bis> -> '[' <exp> ']' <prefixexp_bis>
                             | . <name> <prefixexp_bis>
                             | None

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('\['):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Closing braket expected.", match, '\]')
        parse_prefixexp_bis()
    elif position_set(_save) and match('\.') and parse_name():
        parse_prefixexp_bis()
    else:
        position_set(_save)
        return True

    return True

def parse_args():
    '''
    Parses the production:
            <args> -> ( [<explist>] )
                    | <tableconstructor>
                    | <string>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('\('):
        if parse_explist() and match('\)'):
            return True
        elif match('\)'):
            return True
        else:
            position_set(_save)
            return False
    elif position_set(_save) and parse_tableconstructor():
        return True
    elif position_set(_save) and parse_string():
        return True
    else:
        position_set(_save)
        return False

def parse_var():
    '''
    Parses the production:
            <var>  -> <name>
                    | <prefixexp> '[' <exp> ']'
                    | <prefixexp> . <name>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_prefixexp() and match('\['):
        skip_and_test("Invalid expression.", parse_exp)
        skip_and_test("Closing braket expected.", match, '\]')
        return True
    elif position_set(_save) and parse_prefixexp():
        return True
    elif position_set(_save) and parse_name():
        return True
    else:
        position_set(_save)
        return False

def parse_varlist():
    '''
    Parses the production:
            <varlist> -> <var> {, <var>}

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_var():
        while match(','):
            skip_and_test("Invalid variable.", parse_var)
        red_position()
        return True
    else:
        position_set(_save)
        return False

def parse_exp():
    '''
    Parses the production:
            <exp>  -> nil <exp_bis>
                    | true <exp_bis>
                    | false <exp_bis>
                    | <number> <exp_bis>
                    | <string> <exp_bis>
                    | ... <exp_bis>
                    | <function> <exp_bis>
                    | <prefixexp> <exp_bis>
                    | <tableconstructor> <exp_bis>
                    | <unop> <exp> <exp_bis>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('nil') and parse_exp_bis():
        return True
    elif position_set(_save) and match('false') and parse_exp_bis():
        return True
    elif position_set(_save) and match('true') and parse_exp_bis():
        return True
    elif position_set(_save) and parse_number() and parse_exp_bis():
        return True
    elif position_set(_save) and parse_string() and parse_exp_bis():
        return True
    elif position_set(_save) and parse_tripledot() and parse_exp_bis():
        return True
    elif position_set(_save) and parse_function() and parse_exp_bis():
        return True
    elif position_set(_save) and parse_prefixexp() and parse_exp_bis():
        return True
    elif (position_set(_save) and parse_tableconstructor() and
          parse_exp_bis()):
        return True
    elif (position_set(_save) and parse_unop() and parse_exp() and
          parse_exp_bis()):
        return True
    else:
        position_set(_save)
        return False

def parse_exp_bis():
    '''
    Parses the production:
            <exp_bis>  -> <binop> <exp> <exp_bis>
                        | None

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_binop() and parse_exp():
        parse_exp_bis()
        return True
    else:
        position_set(_save)
        return True

def parse_explist():
    '''
    Parses the production:
            <explist> -> {<exp> ,} <exp>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if parse_exp():
        while match(','):
            skip_and_test("Invalid expression.", parse_exp)
        red_position()
        return True
    else:
        position_set(_save)
        return False

def parse_function():
    '''
    Parses the production:
            <function> -> function <funcbody>

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('function') and parse_funcbody():
        return True
    else:
        position_set(_save)
        return False

def parse_funcbody():
    '''
    Parses the production:
            <funcbody> -> ( [<parlist>] ) <block> end

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    global _function_temp_end, _named_function
    _save = position_get()
    if match('\('):
        _save00 = position_get()
        if parse_parlist():
            skip_and_test("Missing closing parenthesis.", match, '\)')
            if _named_function:
                _function_temp_end = position_get()
                _named_function = False
        else:
            skip_and_test("Missing closing parenthesis", match, '\)')
            if _named_function:
                _function_temp_end = position_get()
                _named_function = False

        parse_block()
        skip_and_test("Invalid statement. Keyword 'end' expected.", match,
                      'end')
        return True
    else:
        position_set(_save)
        return False

def parse_funcname():
    '''
    Parses the production:
            <funcname> -> <name> {. <name>} [: <name>]

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if parse_name():
        while match('\.'):
            if not parse_name():
                error("Invalid identifier after period.")
                if match('\('):
                    red_position()
        red_position()

        if match(':'):
            if not parse_name():
                error("Invalid identifier after colon.")
                if match('\('):
                    red_position()
            return True
        else:
            red_position()
            return True

    else:
        return False

def parse_parlist():
    '''
    Parses the production:
            <parlist>  -> <namelist> [, ...]
                        | ...

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if parse_namelist():
        if match(','):
            skip_and_test("Invalid syntax.", parse_tripledot)
            return True
        else:
            red_position()
            return True
    elif parse_tripledot():
        return True
    else:
        return False

def parse_namelist():
    '''
    Parses the production:
            <namelist> -> <name> {, <name>}

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if parse_name():
        while match(',') and parse_name():
            pass
        red_position()
        return True
    else:
        return False

def parse_number():
    '''
    Checks if the input token is a valid number.

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if match(number):
        return True
    else:
        red_position()
        return False

def parse_string():
    '''
    Checks if the input token is a valid string literal.

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if match(string):
        return True
    else:
        red_position()
        return False

def parse_tripledot():
    '''
    Checks if the input token is a ellipsis (...).

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match('\.') and match('\.') and match('\.'):
        return True
    else:
        position_set(_save)
        return False

def parse_name():
    '''
    Checks if the input token is a valid identifier.

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match(name):
        red_position()
        if not match(keyword):
            return True
        else:
            position_set(_save)
            return False
    else:
        position_set(_save)
        return False

def parse_fieldsep():
    '''
    Checks if the input token is a valid field separator (',', ';').

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if match(fieldsep):
        return True
    else:
        red_position()
        return False

def parse_binop():
    '''
    Checks if the input token is a valid binary operator symbol.

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    _save = position_get()
    if match(binop_1):
        return True
    elif re.fullmatch(binop_2, get_token() + get_next_token()):
        return True
    else:
        position_set(_save)
        if match(binop_3):
            return True
        else:
            position_set(_save)
            return False

def parse_unop():
    '''
    Checks if the input token is a valid unary operator symbol.

        Arguments:
            None

        Output:
            Returns true if the parse could be completed
    '''
    if re.fullmatch(unop, get_next_token()):
        return True
    else:
        red_position()
        return False

def match(string):
    '''
    Shorthand function for matching regular expressions. This is equivalent
    to re.fullmatch(string, get_next_token()) except it returns a boolean
    instead of the matched string.

        Arguments:
            Regular expression pattern.

        Output:
            Returns true if the next token matches the pattern. False otherwise
    '''
    if re.fullmatch(string, get_next_token()):
        return True
    else:
        return False

##############################################################################
# Functions for token pointer movement

def next_statement():
    '''
    Moves the head to the start of the next statement. A new statement is
    detected when a semicolon appears in the input stream or a new line is
    started.

        Arguments:
            None

        Output:
            None
    '''
    _save = position_get()
    while position_get()[0] == _save[0]:
        if re.fullmatch(';', get_next_token()):
            break
    red_position()

def inc_position():
    '''
    Increases header position by one token. This is equivalent to consuming
    the token.

        Arguments:
            None

        Output:
            None
    '''
    global _cl, _ct
    if _ct + 1 >= len(token_list[_cl]):
        if _cl + 1 >= len(token_list):
            _cl = len(token_list) - 1
            _ct = len(token_list[_cl]) - 1
        else:
            _cl += 1
            _ct = 0
    else:
        _ct += 1

    while get_token() == '':
        inc_position()

def red_position():
    '''
    Reduces the header position by one token. This is the opposite to consuming
    a token.

        Arguments:
            None

        Output:
            None
    '''
    global _cl, _ct
    if _ct - 1 < 0:
        if _cl - 1 < 0:
            _cl = 0
            _ct = 0
        else:
            _cl -= 1
            _ct = len(token_list[_cl]) - 1
    else:
        _ct -= 1

    while get_token() == '':
        red_position()

def get_token():
    '''
    Returns the token at the current header position. Note that this does not
    consume the token.

        Arguments:
            None

        Output:
            Current token.
    '''
    return token_list[_cl][_ct]

def get_next_token():
    '''
    Consumes the current token and reads the next token in the input stream.

        Arguments:
            None

        Output:
            Next token.
    '''
    inc_position()
    return get_token()

def position_get():
    '''
    Returns the current position of the header in the input stream. This gives
    a tuple containing the line number and token number.

        Arguments:
            None

        Output:
            Token position with format (<line_number>, <token_number>).
    '''
    return (_cl, _ct)

def position_set(position):
    '''
    Sets the position of the header to the one specified in the argument.

        Arguments:
            Position tuple with format (<line_number>, <token_number>).

        Output:
            Returns true if the no error occured.
            Returns false if an error occured (such as index out of bounds
            error).
    '''
    global _cl, _ct
    try:
        line, token = position
        _cl = line
        _ct = token
        return True
    except:
        return False

##############################################################################
# Error functions

def skip_and_test(error_msg, function, *args, last_stat=False):
    '''
    Tries to execute function <function> with potential arguments <*args>. If
    the function returns a negative value, <error_msg> is stored at current
    head position and input tokens are skipped until a valid parse of the
    function could be made or the statement ends.
    <last_stat> allows to ckeck if the function parsed until the end of the
    statement. This is used in cases where a parse function might return true
    without having parsed the entirety of the desired input stream portion.
    For example in the case:
        repeat
            -- something
        until x 34

    Then we want parse_exp to parse until end of statement and not just parse
    'x' as a valid expression which will raise future errors as the '34' is not
    recognized as an error in the expression but as an error in the next
    statement. Hence <last_stat> = True forces the 34 to be recognized as an
    error in the expression (e.g. missing '>').

        Arguments:
            error_msg:      Error message to be displayed if a parse could not
                            be performed.
            function:       Function used to try parsing the next portion of
                            the input stream.
            *args:          Potential arguments to <function>.
            last_stat:      False by default, complete behaviour described in
                            function description.

        Output:
            Returns True when the function has completed its intended behaviour
    '''
    if not function(*args):
        _save = position_get()
        error(error_msg)

        if args:
            red_position()

        if match(';'):
            return True
        if list(position_get())[0] != _save[0]:
            position_set((_save[0], len(token_list[_save[0]]) - 1))
            return True
    else:
        if last_stat:
            _temp = position_get()
            next_statement()
            if position_get() != _temp:
                error(error_msg, True, _temp)
        return True

    while not function(*args):
        if args:
            red_position()

        if match(';'):
            break

        if get_token() == '___eof___':
            break

        if position_get()[0] != _save[0]:
            position_set((_save[0], len(token_list[_save[0]]) - 1))
            break
    return True


def error(string, placement=False, position=(0, 0)):
    '''
    Stores an error message <string> at position <position> in the input stream
    if <placement> is True. Otherwise <position> is assumed to be the current
    head position when the function is called. Note that errors are saved in
    error_list.

        Arguments:
            string:     Error message to be stored.
            placement:  False by default. Used for custom placement of errors.
                        This is mainly useful when storing the location of a
                        potential error and continuing the parse. If a valid
                        follow up is found, this allows to save the position
                        of the error when having already consumed several
                        tokens beyond the error.
            position:   (0,0) by default. This is the position in the input
                        stream where the error was detected. If <placement>
                        is false, this will be overwritten with the current
                        position of the head when the function was called.

        Output:
            None
    '''
    global error_list
    if not placement:
        position = position_get()

    _temp = list(position)
    _temp.append(string)
    error_list.append(_temp)

def print_errors(filename):
    '''
    Prints "Errors found." and the errors if some are found. Otherwise it will
    print "No errors found.".

        Arguments:
            filename:   File name of the input file. This is used for the error
                        leader.

        Output:
            Prints errors to stdout.
    '''
    if not error_list:
        print("No errors found\n")
    else:
        print("Errors found\n")
        for error in error_list:
            print("{0}, line {1}: {2}".format(filename, error[0], error[2]))
            print_last_tokens(error[0], error[1])

def print_last_tokens(line, token):
    '''
    Parses the production:
            Prints the line an error was found on and pinpoints the location
            of the error with a ^ sign.

        Arguments:
            line:       Line the error was found on.
            token:      Token that generated the error.

        Output:
            Prints to stdout.
    '''
    _sum = 0
    print('\t', end='')
    for _token_number, _token in enumerate(token_list[line]):
        if _token_number < token:
            _sum += len(_token) + 1
        print(_token, end=' ')
    print("{0}{1}{2}".format('\n\t', ' '*(_sum), "^"))

##############################################################################
# Function reporting

def save_function():
    '''
    Saves a function declaration if it is a named function. All named function
    declarations are saved to function_list using positions stored during
    parsing to detect the beginning and the end of the function name and
    parameters.

        Arguments:
            None

        Output:
            None
    '''
    _save = position_get()
    _temp_list = []
    position_set(_function_temp_beg)
    inc_position()
    while True:
        _temp_list.append(get_next_token())
        if position_get() == _function_temp_end:
            break
    function_list.append(_temp_list)

    position_set(_save)

def print_functions():
    '''
    Prints functions stored in function_list to the command line.

        Arguments:
            None

        Output:
            Prints to stdout.
    '''
    print("Declared functions:")
    for _line in function_list:
        print("  ", end='')
        for _token in _line:
            print(_token, end='')
        print()

##############################################################################

# Allow the code to be run as a main script from the command line and take
# an argument from the command line to parse.
if __name__ == "__main__":
    parse(sys.argv[1])
