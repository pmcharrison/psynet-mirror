Fixed ``Column ... conflicts with existing column`` errors when an experiment
class adds a column to a table it shares with other classes, such as a ``Trial``
subclass on Dallinger's ``info`` table. PsyNet now reuses the existing column,
so plain ``Column`` declarations survive reimporting ``experiment.py`` from its
staging copy. Declarations that disagree on type, length, nullability,
uniqueness, indexing, primary key, or foreign-key targets raise a clear error.
