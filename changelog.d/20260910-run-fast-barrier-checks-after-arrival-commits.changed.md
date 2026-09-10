Fast barrier checks now run in a short coordination transaction after the arrival commits, preserving immediate release without holding partner locks through the main request write phase.
