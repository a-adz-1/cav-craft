"""Road grading: no road steeper than a set slope, so climbs come out as slab, block, slab, block."""
import numpy as np


def road_grade(h, on, k):
    """h limited to slope k per cell between 4-neighbours inside `on`: the mean of the upper envelope
    min(h_j + k*d) and the lower envelope max(h_j - k*d). Each is k-Lipschitz, so their mean is too."""
    z = np.nonzero(on.any(1))[0]
    x = np.nonzero(on.any(0))[0]
    sl = np.s_[max(0, z[0] - 1):z[-1] + 2, max(0, x[0] - 1):x[-1] + 2]
    m, hh = on[sl], h[sl].astype(np.float32)
    big = np.float32(1e9)
    U, L = np.where(m, hh, big), np.where(m, hh, -big)
    for it in range(2000):
        U0, L0 = U.copy(), L.copy()
        for a, b in ((np.s_[:, :-1], np.s_[:, 1:]), (np.s_[:, 1:], np.s_[:, :-1]),
                     (np.s_[:-1, :], np.s_[1:, :]), (np.s_[1:, :], np.s_[:-1, :])):
            U[a] = np.where(m[a] & m[b], np.minimum(U[a], U[b] + k), U[a])
            L[a] = np.where(m[a] & m[b], np.maximum(L[a], L[b] - k), L[a])
        if np.array_equal(U, U0) and np.array_equal(L, L0):
            break
    out = h.astype(np.float32).copy()
    out[sl] = np.where(m, (U + L) / 2, hh)
    moved = np.abs(out[sl] - hh)[m]
    print(f"road grade: {it} passes, {int((moved > 0.25).sum())} road cells moved, max {moved.max():.1f} m")
    return out


if __name__ == "__main__":
    t = np.array([[0, 0, 3, 3, 0, 0]], np.float32)                 # a 3 m kerb-like jump gets graded
    g = road_grade(t, np.ones_like(t, bool), 0.5)
    assert np.abs(np.diff(g)).max() <= 0.5 + 1e-6 and np.abs(np.diff(np.floor(g + 0.5))).max() <= 1, g
    print("grade ok")
