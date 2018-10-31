# Copyright (c) 2018 HarryR
# License: LGPL-3.0+
"""
Converts SHDL (Secure Hardware Definition Language) files generated by
the FairPlay SFDL compiler into the 'Extended Pinocchio' format usable
with EthSnarks.

Types of gates:

 * input
 * intermediate gate
 * output gate

There are a number of oddities which don't directly translate to the
Pinocchio format, especially with the unoptimised form of the circuit.

## Example 1:

	0 gate arity 0 table [0] inputs [] // false
	1 gate arity 0 table [1] inputs [] //true

These are affirmations, they affirm that the value of the wire is always
a specific value. This is equivalent to a constant value.

## Example 2:

	511 output gate arity 1 table [ 0 1 ] inputs [ 510 ]	//output$output.bob$0

This is equivalent to a pass-thru gate, it maps 0 to 0 and 1 to 1.
It can be optimised-out, when translating to Pinocchio the input wire (510)
is remapped to the output wire (511). The mapping is done in reverse, from
511 to 510, so any gate which references 511 as an input will be remapped
to access 510 instead.

This is often used to copy a value to another, where an output is duplicated,
for example, if the same expression is used as both output values, only one
will be computed and the other will be copied using an example of the statement
above.

When both gates are outputs (e.g. passthru of an output to an output) it can
be ignored.

## Example 3:

	289 gate arity 1 table [ 1 0 ] inputs [ 2 ]

This is a 'not' gate, translated into a truth table.
"""

from __future__ import print_function
import re
import sys
from collections import namedtuple, OrderedDict


RE_VAR_LINE = re.compile(r'(?P<party>Alice|Bob) (input|output) (?P<type>integer) "(?P<name>[^"]+)" \[\s*(?P<inputs>([0-9]+\s)+)\]')


_VariableStruct = namedtuple('_VariableStruct', (
	'party',
	'type',
	'name',
	'wires'))


class Variable(_VariableStruct):
	@classmethod
	def from_line(cls, line, lineno):
		m = RE_VAR_LINE.match(line)
		return cls(
			m.group('party'),
			m.group('type'),
			m.group('name'),
			[int(_) for _ in m.group('inputs').strip().split()])


_GateStruct = namedtuple('_GateStruct', (
	'is_input',
	'is_output',
	'wire',
	'arity',
	'table',
	'inputs',
	'comment'))


RE_GATE_LINE = re.compile(r'^(?P<wire>[0-9]+) ((?P<is_output>output )?gate arity (?P<arity>[0-9]+) table \[\s(?P<table>([01]\s?)+)\] inputs \[\s(?P<inputs>[0-9]+\s)+\]|(?P<is_input>input))(?P<comment>\s*//.*)?$')


class Gate(_GateStruct):
	def is_constant(self):
		"""
		Does the gate restrict the output value to a constant value?
		e.g. a gate with arity 0 will always map to the same value.
		"""
		return self.arity == 0

	def is_passthru(self):
		"""
		Does the gate act as a passthru?
		Where any input bit will result in the same output bit
		"""
		return self.arity == 1 and self.table == [0, 1]

	def is_not(self):
		"""
		Does the gate as act a NOT() statement?
		Where the output bit will be the inverse of the input bit.
		e.g. 0 -> 1, and 1 -> 0
		"""
		return self.arity == 1 and self.table == [1, 0]

	@classmethod
	def from_line(cls, line, lineno):
		"""
		Convert a line of text into a parsed gate
		"""
		line = line.strip()
		m = RE_GATE_LINE.match(line)
		if m is None:
			print("Error on line ", lineno)
			print("Line: ", line)
			return None

		comment = m.group('comment')
		if comment:
			comment = comment.strip()[2:]

		wire = int(m.group('wire'))

		is_input = m.group('is_input') == 'input'

		arity = m.group('arity')
		if arity is not None:
			arity = int(arity)
			if arity < 0 or arity > 3:
				print("Error on line ", lineno)
				print("Line: ", line)
				print("Gate arity %d not supported!" % (arity,))
				return None

		table = m.group('table')
		if table:
			table = [int(_) for _ in table.split()]

		inputs = m.group('inputs')
		if inputs:
			inputs = [int(_) for _ in inputs.split()]

		is_output = m.group('is_output') == 'output '

		if not is_input:
			if len(table) != 1<<arity:
				print("Error on line ", lineno)
				print("Line: ", line)
				print("Expected table of %d bits for arity %d, got table of %d bits instead!", 1<<arity, arity, len(table))
				return None

		return cls(
			is_input,
			is_output,
			wire,
			arity,
			table,
			inputs,
			comment)


def parse_gates(file_handle):
	"""
	Given a Secure Hardware Definition Language circuit file
	Return an ordered dictionary of all wires mapped to their gates
	"""
	wires = OrderedDict()

	for lineno, line in enumerate(file_handle):
		line = line.strip()
		if not line:
			continue

		parsed = Gate.from_line(line, lineno)
		if not parsed:
			return 2

		if parsed.wire in wires:
			print("Error on line ", lineno)
			print("Line: ", line)
			print("Duplicate wire: ", parsed.wire)
			return 3

		wires[parsed.wire] = parsed

	return wires


def parse_variables(file_handle):
	variables = OrderedDict()

	for lineno, line in enumerate(file_handle):
		line = line.strip()
		if not line:
			continue
		parsed = Variable.from_line(line, lineno)
		variables[ parsed.name ] = parsed

	return variables


def main(args):
	if len(args) < 2:
		print("Usage: shdl2ethsnarks.py <file.circuit> <file.fmt>")
		return 1

	with open(args[0], 'r') as handle:
		wires = parse_gates(handle)

	with open(args[1], 'r') as handle:
		variables = parse_variables(handle)

	print(wires)
	print(variables)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))