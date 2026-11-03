def moves(i: i64, a: i64, low: view[i64], high: view[i64]) -> (first: i64, count: i64) can[Abort.Panic]:
    first: i64 =
        lowest: i64 = low[i] if low[i] > 1 else 1
        low[i + 1] + 1 - a if low[i + 1] + 1 - a > lowest else lowest
    last: i64 = high[i] if high[i] < high[i + 1] + 1 - a else high[i + 1] + 1 - a
    return first, (last - first + 1 if last >= first else 0)

# One-shot banded sum and maximum, with an empty result for no accepted path.
# A NaN result signals overflow while adding finite log weights.
def banded_format(log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    count: i64 = alphabet.len.i64()
    m: i64 = low.len.i64() - 1
    return [] if high.len.i64() != m + 1 or not matrix_shape(log_probs.len.i64(), m, count)
    return [] if low[0] > 1 or high[0] < 1 or low[m] > 0 or high[m] < 0
    width: i64 = m + 2
    missing: f64 = log(0.0)
    forward: darray[f64] = [0.0 if i == 1 else missing for i in 0..<(2 * width)]
    best: darray[f64] = [0.0 if i == 1 else missing for i in 0..<(2 * width)]
    choice: darray[i64] = [0 for _ in 0..<((m + 1) * width)]
    for k in 0..<m:
        here: i64 = (k % 2) * width
        next: i64 = ((k + 1) % 2) * width
        for state in low[k + 1]..<(high[k + 1] + 1):
            forward[next + state] <- missing
            best[next + state] <- missing
        for j in 0..<count:
            arity: i64 = alphabet[j]
            return [] if arity < 0
            step: f64 = log_probs[k * count + j]
            continue if step == missing
            run: (first: i64, count: i64) = moves(k, arity, low, high)
            for t in 0..<run.count:
                state: i64 = run.first + t
                target: i64 = state - 1 + arity
                if forward[here + state] != missing:
                    incoming: f64 = forward[here + state] + step
                    return [log(-1.0)] if incoming == missing or incoming == -missing or incoming != incoming
                    forward[next + target] <- log_add(forward[next + target], incoming)
                if best[here + state] != missing:
                    candidate: f64 = best[here + state] + step
                    return [log(-1.0)] if candidate == missing or candidate == -missing or candidate != candidate
                    if candidate > best[next + target]:
                        best[next + target] <- candidate
                        choice[(k + 1) * width + target] <- j
    log_z: f64 = forward[(m % 2) * width]
    return [] if log_z == missing
    result: darray[f64] = [0.0 for _ in 0..<(m + 2)]
    result[0] <- log_z
    result[1] <- best[(m % 2) * width]
    trace_state: darray[i64] = [0]
    for step in 0..<m:
        k: i64 = m - step
        arity: i64 = alphabet[choice[k * width + trace_state[0]]]
        result[1 + k] <- arity.f64()
        trace_state[0] <- trace_state[0] + 1 - arity
    return result

# Enclose all reachable sum or maximum states; interior holes are retained.
def support_envelope(sums: view[f64], maxima: view[f64], offsets: view[i64], low: view[i64], high: view[i64], row: i64) -> (first: i64, last: i64) can[Abort.Panic]:
    first: i64 =
        for n in low[row]..<(high[row] + 1) |first: i64 = high[row] + 1| -> first:
            index: i64 = offsets[row] + n - low[row]
            if sums[index] != log(0.0) or maxima[index] != log(0.0):
                first <- n
                break
    last: i64 =
        for back in 0..<(high[row] - first + 1) |last: i64 = first - 1| -> last:
            n: i64 = high[row] - back
            index: i64 = offsets[row] + n - low[row]
            if sums[index] != log(0.0) or maxima[index] != log(0.0):
                last <- n
                break
    return first, last

def arities_ordered(alphabet: view[i64]) -> bool can[Abort.Panic]:
    for j in 1..<alphabet.len.i64():
        return false if alphabet[j] < alphabet[j - 1]
    return true

# Recompute forward and backward rows in log space.
def advance_ragged_log(forward: mutable view[f64], forward_max: mutable view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], start: i64, stop: i64) -> i64 can[Abort.Panic]:
    arities: i64 = alphabet.len.i64()
    ordered: bool = arities_ordered(alphabet)
    for i in start..<stop:
        target: i64 = offsets[i + 1]
        for n in low[i + 1]..<(high[i + 1] + 1):
            forward[target + n - low[i + 1]] <- log(0.0)
            forward_max[target + n - low[i + 1]] <- log(0.0)
        active: (first: i64, last: i64) = support_envelope(forward, forward_max, offsets, low, high, i)
        continue if active.first > active.last
        minimum: i64 = active.first if active.first > 1 else 1
        for j in 0..<arities:
            break if ordered and alphabet[j] > high[i + 1] + 1 - minimum
            step: f64 = log_probs[i * arities + j]
            continue if step == log(0.0)
            run: (first: i64, count: i64) = moves(i, alphabet[j], low, high)
            first: i64 = run.first if run.first > active.first else active.first
            end: i64 = (run.first + run.count) if run.first + run.count < active.last + 1 else active.last + 1
            for n in first..<end:
                source: i64 = offsets[i] + n - low[i]
                cell: i64 = target + n - 1 + alphabet[j] - low[i + 1]
                if forward[source] != log(0.0):
                    incoming: f64 = forward[source] + step
                    return -1 if incoming == log(0.0) or incoming == -log(0.0) or incoming != incoming
                    forward[cell] <- incoming if forward[cell] == log(0.0) else log_add_present(forward[cell], incoming)
                candidate: f64 = forward_max[source] + step
                return -1 if forward_max[source] != log(0.0) and (candidate == log(0.0) or candidate == -log(0.0) or candidate != candidate)
                forward_max[cell] <- candidate if candidate > forward_max[cell] else forward_max[cell]
    return stop - start

def retreat_ragged_log(backward: mutable view[f64], backward_max: mutable view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], start: i64, stop: i64) -> i64 can[Abort.Panic]:
    arities: i64 = alphabet.len.i64()
    ordered: bool = arities_ordered(alphabet)
    for back in 0..<(start - stop):
        i: i64 = start - 1 - back
        for n in low[i]..<(high[i] + 1):
            backward[offsets[i] + n - low[i]] <- log(0.0)
            backward_max[offsets[i] + n - low[i]] <- log(0.0)
        active: (first: i64, last: i64) = support_envelope(backward, backward_max, offsets, low, high, i + 1)
        continue if active.first > active.last
        minimum: i64 = low[i] if low[i] > 1 else 1
        for j in 0..<arities:
            break if ordered and alphabet[j] > active.last + 1 - minimum
            step: f64 = log_probs[i * arities + j]
            continue if step == log(0.0)
            run: (first: i64, count: i64) = moves(i, alphabet[j], low, high)
            active_first: i64 = active.first + 1 - alphabet[j]
            active_end: i64 = active.last + 2 - alphabet[j]
            first: i64 = run.first if run.first > active_first else active_first
            end: i64 = (run.first + run.count) if run.first + run.count < active_end else active_end
            for n in first..<end:
                cell: i64 = offsets[i] + n - low[i]
                source: i64 = offsets[i + 1] + n - 1 + alphabet[j] - low[i + 1]
                if backward[source] != log(0.0):
                    incoming: f64 = backward[source] + step
                    return -1 if incoming == log(0.0) or incoming == -log(0.0) or incoming != incoming
                    backward[cell] <- incoming if backward[cell] == log(0.0) else log_add_present(backward[cell], incoming)
                candidate: f64 = backward_max[source] + step
                return -1 if backward_max[source] != log(0.0) and (candidate == log(0.0) or candidate == -log(0.0) or candidate != candidate)
                backward_max[cell] <- candidate if candidate > backward_max[cell] else backward_max[cell]
    return start - stop

# [log Z, best log weight] with symbol k replaced by log_row. The ordered flag
# may be true only if the supplied alphabet is nondecreasing.
def scores_ragged_with_order(forward: view[f64], forward_max: view[f64], backward: view[f64], backward_max: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64, log_row: view[f64], ordered: bool) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    left: (first: i64, last: i64) = support_envelope(forward, forward_max, offsets, low, high, k)
    right: (first: i64, last: i64) = support_envelope(backward, backward_max, offsets, low, high, k + 1)
    return [log(0.0), log(0.0)] if left.first > left.last or right.first > right.last
    minimum: i64 = left.first if left.first > 1 else 1
    total, log_x =
        for j in 0..<alphabet.len.i64() |total: f64 = log(0.0), log_x: f64 = log(0.0)| -> (total, log_x):
            break if ordered and alphabet[j] > right.last + 1 - minimum
            continue if log_row[j] == log(0.0)
            run: (first: i64, count: i64) = moves(k, alphabet[j], low, high)
            first_left: i64 = run.first if run.first > left.first else left.first
            first_right: i64 = right.first + 1 - alphabet[j]
            first: i64 = first_left if first_left > first_right else first_right
            end_left: i64 = (run.first + run.count) if run.first + run.count < left.last + 1 else left.last + 1
            end_right: i64 = right.last + 2 - alphabet[j]
            end: i64 = end_left if end_left < end_right else end_right
            for n in first..<end |total, log_x|:
                here: i64 = offsets[k] + n - low[k]
                next: i64 = offsets[k + 1] + n - 1 + alphabet[j] - low[k + 1]
                if forward[here] != log(0.0) and backward[next] != log(0.0):
                    partial: f64 = forward[here] + log_row[j]
                    return [log(-1.0), log(-1.0)] if partial == log(0.0) or partial == -log(0.0) or partial != partial
                    incoming: f64 = partial + backward[next]
                    return [log(-1.0), log(-1.0)] if incoming == log(0.0) or incoming == -log(0.0) or incoming != incoming
                    total <- incoming if total == log(0.0) else log_add_present(total, incoming)
                if forward_max[here] != log(0.0) and backward_max[next] != log(0.0):
                    partial: f64 = forward_max[here] + log_row[j]
                    return [log(-1.0), log(-1.0)] if partial == log(0.0) or partial == -log(0.0) or partial != partial
                    candidate: f64 = partial + backward_max[next]
                    return [log(-1.0), log(-1.0)] if candidate == log(0.0) or candidate == -log(0.0) or candidate != candidate
                    log_x <- candidate if candidate > log_x else log_x
    return [total, log_x]

# Compatibility entry point determines the ordering on each call.
def scores_ragged_log(forward: view[f64], forward_max: view[f64], backward: view[f64], backward_max: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64, log_row: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return scores_ragged_with_order(forward, forward_max, backward, backward_max, alphabet, low, high, offsets, k, log_row, arities_ordered(alphabet))

# [best log weight, its arities (m)], with forward max row `k` and backward max row `k + 1`
# current (THEORY §23.4, Theorem 23.10): the best state and arity at symbol `k`, then the best
# prefix traced back through the forward max rows and the best suffix forward through the
# backward max rows.
# Indexed traversal requires a permutation sorted by the supplied arities.
def trace_ragged_core(forward_max: view[f64], backward_max: view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64, ordered: bool, indices: view[i64], indexed: bool) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    arities: i64 = alphabet.len.i64()
    m: i64 = low.len.i64() - 1
    left: (first: i64, last: i64) = support_envelope(forward_max, forward_max, offsets, low, high, k)
    right: (first: i64, last: i64) = support_envelope(backward_max, backward_max, offsets, low, high, k + 1)
    log_x, state, choice =
        for j in 0..<arities |log_x: f64 = log(0.0), state: i64 = 0, choice: i64 = 0| -> (log_x, state, choice):
            reading: f64 = log_probs[k * arities + j]
            continue if reading == log(0.0)
            run: (first: i64, count: i64) = moves(k, alphabet[j], low, high)
            first_left: i64 = run.first if run.first > left.first else left.first
            first_right: i64 = right.first + 1 - alphabet[j]
            first: i64 = first_left if first_left > first_right else first_right
            end_left: i64 = (run.first + run.count) if run.first + run.count < left.last + 1 else left.last + 1
            end_right: i64 = right.last + 2 - alphabet[j]
            end: i64 = end_left if end_left < end_right else end_right
            for n in first..<end |log_x, state, choice|:
                prefix: f64 = forward_max[offsets[k] + n - low[k]]
                suffix: f64 = backward_max[offsets[k + 1] + n - 1 + alphabet[j] - low[k + 1]]
                continue if prefix == log(0.0) or suffix == log(0.0)
                partial: f64 = prefix + reading
                return [log(-1.0)] if partial == log(0.0) or partial == -log(0.0) or partial != partial
                candidate: f64 = partial + suffix
                return [log(-1.0)] if candidate == log(0.0) or candidate == -log(0.0) or candidate != candidate
                if candidate > log_x:
                    log_x <- candidate
                    state <- n
                    choice <- j
    return [log_x] if log_x == log(0.0)
    result: darray[f64] = [0.0 for i in 0..<(m + 1)]
    result[0] <- log_x
    result[1 + k] <- alphabet[choice].f64()
    for back in 0..<k |before: i64 = state|:
        i: i64 = k - 1 - back
        best, source, arity, _ =
            for position in 0..<arities |best: f64 = log(0.0), source: i64 = 1, arity: i64 = 0, best_index: i64 = arities| -> (best, source, arity, best_index):
                j: i64 = indices[position] if indexed else position
                n: i64 = before + 1 - alphabet[j]
                if n < 1 or n < low[i]:
                    break if ordered
                    continue
                continue if n > high[i]
                candidate: f64 = forward_max[offsets[i] + n - low[i]] + log_probs[i * arities + j]
                if candidate > best or (indexed and candidate == best and candidate != log(0.0) and j < best_index):
                    best <- candidate
                    source <- n
                    arity <- alphabet[j]
                    best_index <- j
        result[1 + i] <- arity.f64()
        before <- source
    for i in (k + 1)..<m |after: i64 = state - 1 + alphabet[choice]|:
        best, target, arity, _ =
            for position in 0..<arities |best: f64 = log(0.0), target: i64 = 0, arity: i64 = 0, best_index: i64 = arities| -> (best, target, arity, best_index):
                j: i64 = indices[position] if indexed else position
                continue if after < 1
                if alphabet[j] > high[i + 1]:
                    break if ordered
                    continue
                n: i64 = after - 1 + alphabet[j]
                if n > high[i + 1]:
                    break if ordered
                    continue
                continue if n < low[i + 1]
                candidate: f64 = log_probs[i * arities + j] + backward_max[offsets[i + 1] + n - low[i + 1]]
                if candidate > best or (indexed and candidate == best and candidate != log(0.0) and j < best_index):
                    best <- candidate
                    target <- n
                    arity <- alphabet[j]
                    best_index <- j
        result[1 + i] <- arity.f64()
        after <- target
    return result

# The ordered flag may be true only for a nondecreasing alphabet.
def trace_ragged_with_order(forward_max: view[f64], backward_max: view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64, ordered: bool) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return trace_ragged_core(forward_max, backward_max, log_probs, alphabet, low, high, offsets, k, ordered, alphabet, false)

# indices must be a permutation of the alphabet indices sorted by their arities.
def trace_ragged_indexed(forward_max: view[f64], backward_max: view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64, indices: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return trace_ragged_core(forward_max, backward_max, log_probs, alphabet, low, high, offsets, k, true, indices, true)

# Compatibility entry point determines the ordering on each call.
def trace_ragged(forward_max: view[f64], backward_max: view[f64], log_probs: view[f64], alphabet: view[i64], low: view[i64], high: view[i64], offsets: view[i64], k: i64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return trace_ragged_with_order(forward_max, backward_max, log_probs, alphabet, low, high, offsets, k, arities_ordered(alphabet))

# Check a prefix tree of arbitrary nonnegative arities without building it.
def valid_prefix(arities: view[i64]) -> bool can[Abort.Panic]:
    m: i64 = arities.len.i64()
    return false if m == 0
    pending: i64 =
        for k in 0..<m |pending: i64 = 1| -> pending:
            arity: i64 = arities[k]
            # The previous step ensures pending <= m - k, so this guard
            # bounds the next counter before performing the addition.
            return false if pending == 0 or arity < 0 or arity > m - k - pending
            pending <- pending - 1 + arity
    return pending == 0

# Parse arities 0, 1, 2 into two child slots per symbol; empty means invalid.
def parse_tree(arities: view[i64]) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = arities.len.i64()
    return [] if m == 0
    result, remaining =
        for k in 0..<m |result: darray[i64] = [-1 for _ in 0..<(2 * m)], parents: darray[i64] = [0 for _ in 0..<m], missing: darray[i64] = [0 for _ in 0..<m], depth: i64 = 0| -> (result, depth):
            return [] if arities[k] < 0 or arities[k] > 2
            if k > 0:
                return [] if depth == 0
                parent: i64 = parents[depth - 1]
                slot: i64 = 2 * parent + (0 if result[2 * parent] < 0 else 1)
                result[slot] <- k
                missing[depth - 1] <- missing[depth - 1] - 1
                depth <- depth - 1 if missing[depth - 1] == 0 else depth
            if arities[k] > 0:
                parents[depth] <- k
                missing[depth] <- arities[k]
                depth += 1
    return result if remaining == 0 else []

# Parse general arities into offsets followed by contiguous child indices.
def parse_tree_generic(arities: view[i64]) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = arities.len.i64()
    return [] if m == 0
    offsets: darray[i64] = [0 for _ in 0..<(m + 1)]
    for k in 0..<m:
        arity: i64 = arities[k]
        return [] if arity < 0 or arity > m - 1 - offsets[k]
        offsets[k + 1] <- offsets[k] + arity
    return [] if offsets[m] != m - 1
    result, remaining =
        for k in 0..<m |result: darray[i64] = [offsets[i] if i <= m else 0 for i in 0..<(2 * m)], parents: darray[i64] = [0 for _ in 0..<m], missing: darray[i64] = [0 for _ in 0..<m], depth: i64 = 0| -> (result, depth):
            if k > 0:
                return [] if depth == 0
                parent: i64 = parents[depth - 1]
                slot: i64 = m + 1 + offsets[parent] + arities[parent] - missing[depth - 1]
                result[slot] <- k
                missing[depth - 1] <- missing[depth - 1] - 1
                depth <- depth - 1 if missing[depth - 1] == 0 else depth
            if arities[k] > 0:
                parents[depth] <- k
                missing[depth] <- arities[k]
                depth += 1
    return result if remaining == 0 else []

# Sum nonnegative finite row masses into caller-declared groups. Compensated
# additions match Python's floating-point sum on the runtime's float tuples.
