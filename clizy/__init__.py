from argparse import ArgumentParser
from inspect import signature, Parameter, cleandoc
from itertools import chain
from typing import NamedTuple, Any, List, Dict


def _replace_underscores_with_dashes(string: str):
    return string.replace('_', '-')


class Option:
    def __init__(self, original_name, name, short_name, default, type, description):
        self.original_name = original_name
        self.name = name
        self.short_name = short_name
        self.default = default
        self.type = type
        self.description = description


class Argument(NamedTuple):
    name: str
    type: Any
    description: str


class Interface(NamedTuple):
    name: str
    description: str
    arguments: Dict[str, Argument]
    options: Dict[str, Option]


def simple_docstring_processor(docstring, interface: Interface):
    interface.description = docstring


class ClizyError(Exception):
    pass


class UnsupportedTypeError(ClizyError):
    pass


class Clizy:
    _SUPPORTED_TYPES = {int, str, bool, float}
    _SUPPORTED_COMPLEX_TYPES = {list, List[int], List[float], List[str]}

    def __init__(self, docstring_processor=simple_docstring_processor):
        self._docstring_processor = docstring_processor

    def _process_docstring(self, docstring, interface: Interface):
        if docstring is None:
            return

        cleaned_docstring = cleandoc(docstring)
        return self._docstring_processor(cleaned_docstring, interface)

    def _prepare_function(self, func):
        options = {}
        arguments = {}

        func_signature = signature(func)
        param: Parameter

        for param in func_signature.parameters.values():
            original_name = param.name
            name = _replace_underscores_with_dashes(original_name)
            expected_type = param.annotation

            default = param.default

            default_is_empty = default is Parameter.empty

            if expected_type is list:
                expected_type = List[str]

            if expected_type is bool and default_is_empty:
                default = False
                default_is_empty = False

            if isinstance(default, bool) and expected_type is Parameter.empty:
                expected_type = bool

            if expected_type == Parameter.empty:
                expected_type = str

            if expected_type not in self._SUPPORTED_TYPES and expected_type not in self._SUPPORTED_COMPLEX_TYPES:
                raise UnsupportedTypeError(expected_type)

            if not default_is_empty:
                option = Option(original_name, name, None, default, expected_type, None)
                options[original_name] = option

            else:
                argument = Argument(name, expected_type, None)
                arguments[original_name] = argument

        self._assign_short_names(options.values())

        func_name = _replace_underscores_with_dashes(func.__name__)

        interface = Interface(func_name, None, arguments, options)
        self._process_docstring(func.__doc__, interface)

        return interface

    def _setup_parser(self, parser: ArgumentParser, interface: Interface):
        for option in interface.options.values():
            kwargs = {
                'default': option.default,
                'dest': option.original_name
            }

            if option.type is bool:
                kwargs['action'] = 'store_true'
            else:
                kwargs['type'] = option.type

            if option in self._SUPPORTED_COMPLEX_TYPES:
                kwargs['nargs'] = '*'

            parser.add_argument(
                f'-{option.short_name}', f'--{option.name}', **kwargs
            )

        complex_type_count = 0
        for argument in interface.arguments.values():
            kwargs = {
                # dest is first argument for positional arguments, can't be set
                #'dest': argument.original_name
            }

            argument_type = argument.type
            if argument_type in self._SUPPORTED_COMPLEX_TYPES:
                if complex_type_count > 1:
                    raise Exception

                complex_type_count += 1

                argument_type = argument_type.__args__[0]
                kwargs['nargs'] = '+'

            kwargs['type'] = argument_type

            parser.add_argument(
                argument.name, **kwargs
            )

    def _assign_short_names(self, options):
        used_letters = {'h', '-'}

        for option in options:
            for letter in chain.from_iterable(zip(option.name, option.name.upper())):
                if letter not in used_letters:
                    used_letters.add(letter)
                    option.short_name = letter
                    break

            if not option.short_name:
                raise Exception

    def run_function(self, func, argv=None):
        """

        :param func:
        :param argv:
        :return:
        """
        interface = self._prepare_function(func)

        parser = ArgumentParser(prog=interface.name, description=interface.description)
        self._setup_parser(parser, interface)

        arguments = parser.parse_args(argv)
        kwargs = vars(arguments)

        return func(**kwargs)

    def run_functions(self, *funcs, argv=None):
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(dest='clizy_subparser_name')

        for func in funcs:
            interface = self._prepare_function(func)

            subparser_name = interface.name
            subparser = subparsers.add_parser(subparser_name)

            self._setup_parser(subparser, interface)

        arguments = parser.parse_args(argv)
        kwargs = vars(arguments)
        func_name = kwargs.pop('clizy_subparser_name')

        for func in funcs:
            if func.__name__ == func_name:
                func(**kwargs)


def run(func, argv=None):
    return Clizy().run_function(func, argv=argv)


def run_funcs(*funcs, argv=None):
    return Clizy().run_functions(*funcs, argv=None)


if __name__ == '__main__':
    def ls(filename, long: bool, all: bool, human_readable: bool, limit: int=None):
        """
        Fake command for listing.
        """
        print(vars())

    run(ls, argv=['--help'])
    #run(ls, argv=['--all', '-H', 'file.txt'])
    #run(ls, argv=['-L=42', 'file.txt'])
