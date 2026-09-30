"""
native_engine/rng.py - Canonical Deterministic PRNG
Implements the canonical 48-bit linear congruential generator (LCG)
matching Java's java.util.Random.nextDouble() and 182 Util.rand() floating-point scaling.
"""

class NativeRng:
    def __init__(self, seed: int):
        self.initial_seed = seed
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)
        self.call_count = 0
        self.call_history = []

    def _next(self, bits: int) -> int:
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return self.seed >> (48 - bits)

    def next_double(self) -> float:
        return ((self._next(26) << 27) + self._next(27)) / float(1 << 53)

    def rand(self, lbound: int, ubound: int, callsite: str = "") -> int:
        """
        182 Canonical rand formula:
        int range = ubound - lbound + 1;
        result = (int)(nextDouble() * range + lbound);
        """
        self.call_count += 1
        r = ubound - lbound + 1
        res = int(self.next_double() * r + lbound)
        self.call_history.append({
            "call_index": self.call_count,
            "callsite": callsite,
            "min": lbound,
            "max": ubound,
            "result": res
        })
        return res
