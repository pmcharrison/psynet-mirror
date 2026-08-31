# README

A small computerized adaptive test (CAT) for mental arithmetic. Each
participant answers four-choice questions. After each scored response, a 1PL
Rasch model updates a grid posterior over ability and the next item is the
unused question with the highest expected Fisher information.

The demo is meant as a worked example of participant-level adaptation with
`Trial.cue`, a dedicated decision table, and a PsyNet-free `adaptive_logic.py`
shared with `simulate_procedure.py`.

## Usage

For instructions on how to run PsyNet experiments like this one, visit the
[PsyNet documentation](https://psynetdev.gitlab.io/PsyNet/).
