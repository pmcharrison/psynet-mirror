Timeline requests now commit state changes before rendering in a read-only transaction, preventing template work from holding database write locks.
