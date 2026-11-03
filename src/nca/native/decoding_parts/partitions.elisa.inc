def decode(log_probs: view[f64], alphabet: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    return [FLOOR] if width == 0 or log_probs.len.i64() % width != 0
    m: i64 = log_probs.len.i64() / width
    return [FLOOR] if m == 0
    for j in 0..<width:
        return [FLOOR] if alphabet[j] < 0
    max_arity: i64 =
        for j in 0..<width |largest: i64 = 0| -> largest:
            largest <- alphabet[j] if alphabet[j] > largest and alphabet[j] < m else largest
    row_size: i64 = m + 1
    offsets: darray[i64] =
        for k in 0..<(m + 1) |offsets: darray[i64] = [0 for _ in 0..<(m + 2)]| -> offsets:
            offsets[k + 1] <- offsets[k] + live(k, m, max_arity) + 1
    # Subnormal weights lose relative precision, and finite weights may vanish.
    # Signal the caller to rerun the whole calculation in log space.
    weights: darray[f64] = [0.0 for _ in 0..<(m * width)]
    for k in 0..<m:
        for j in 0..<width:
            continue if alphabet[j] >= m - k
            i: i64 = k * width + j
            weight: f64 = exp(log_probs[i])
            return [FLOOR] if log_probs[i] != log(0.0) and weight < 2.2250738585072014e-308
            return [FLOOR] if weight == -log(0.0)
            weights[i] <- weight
    forward, best, choice, totals, log_z =
        for k in 0..<m |forward: darray[f64] = [1.0 if i == offsets[0] + 1 else 0.0 for i in 0..<offsets[m + 1]], best: darray[f64] = [0.0 if i == 1 else FLOOR for i in 0..<(2 * row_size)], choice: darray[i64] = [0 for _ in 0..<offsets[m + 1]], totals: darray[f64] = [1.0 for _ in 0..<(m + 1)], log_z: f64 = 0.0| -> (forward, best, choice, totals, log_z):
            best_here: i64 = (k % 2) * row_size
            best_next: i64 = ((k + 1) % 2) * row_size
            best[best_here] <- FLOOR
            total: f64 = |forward, best, choice|
                next_row: i64 = offsets[k + 1]
                next_top: i64 = live(k + 1, m, max_arity)
                for n in 1..<(live(k, m, max_arity) + 1) |forward, best, choice|:
                    here_best: f64 = best[best_here + n]
                    # The consumed row becomes the empty destination two steps later.
                    best[best_here + n] <- FLOOR
                    continue if here_best <= FLOOR
                    here: f64 = forward[offsets[k] + n] / totals[k]
                    for j in 0..<width |forward, best, choice|:
                        continue if alphabet[j] > next_top
                        target: i64 = n - 1 + alphabet[j]
                        continue if target > next_top or (target == 0 and k + 1 < m)
                        cell: i64 = next_row + target
                        weight: f64 = weights[k * width + j]
                        contribution: f64 = here * weight
                        return [FLOOR] if here > 0.0 and weight > 0.0 and contribution < 2.2250738585072014e-308
                        forward[cell] <- forward[cell] + contribution
                        candidate: f64 = here_best + log_probs[k * width + j]
                        choice[cell] <- j if candidate > best[best_next + target] or (candidate == best[best_next + target] and j < choice[cell]) else choice[cell]
                        best[best_next + target] <- candidate if candidate > best[best_next + target] else best[best_next + target]
                for n in 0..<(next_top + 1) |total: f64 = 0.0| -> total:
                    total += forward[next_row + n]
            totals[k + 1] <- 1.0 if total <= 0.0 else total
            log_z <- FLOOR if total <= 0.0 or log_z <= FLOOR else log_z + log(total)
    return [FLOOR] if log_z <= FLOOR or best[(m % 2) * row_size] <= FLOOR
    decoded: darray[f64] =
        for step in 0..<m |decoded: darray[f64] = [log_z if i == 0 else 0.0 for i in 0..<(1 + m + m * width)], state: i64 = 0| -> decoded:
            arity: i64 = alphabet[choice[offsets[m - step] + state]]
            decoded[m - step] <- arity.f64()
            state <- state + 1 - arity
    result: darray[f64] =
        for step in 0..<m |result: darray[f64] = decoded, backward: darray[f64] = [1.0 if i == (m % 2) * row_size else 0.0 for i in 0..<(2 * row_size)]| -> result:
            k: i64 = m - 1 - step
            here_row: i64 = offsets[k]
            backward_here: i64 = (k % 2) * row_size
            backward_next: i64 = ((k + 1) % 2) * row_size
            next_top: i64 = live(k + 1, m, max_arity)
            for n in 0..<(live(k, m, max_arity) + 1) |backward|:
                backward[backward_here + n] <- 0.0
            for j in 0..<width |result, backward|:
                continue if alphabet[j] > next_top
                through_total: f64 = |backward|
                    weight: f64 = weights[k * width + j] / totals[k + 1]
                    return [FLOOR] if weight == -log(0.0)
                    for n in 1..<(live(k, m, max_arity) + 1) |backward, through_total: f64 = 0.0| -> through_total:
                        continue if forward[here_row + n] == 0.0
                        through: f64 =
                            target: i64 = n - 1 + alphabet[j]
                            continue if target > next_top or (target == 0 and k + 1 < m)
                            weight * backward[backward_next + target]
                        return [FLOOR] if through == -log(0.0) or through != through
                        backward[backward_here + n] <- backward[backward_here + n] + through
                        return [FLOOR] if backward[backward_here + n] == -log(0.0)
                        through_total += forward[here_row + n] * through
                result[1 + m + k * width + j] <- through_total / totals[k]
    return result

# Product of prior edge and final weights, in log space (NCA.prior, §27).
def prior_log_weight(alphabet: view[i64], transitions: view[i64], weights: view[f64], final: view[f64], start: i64, selected: view[i64]) -> f64 can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    indexed: bool =
        for j in 0..<width |valid: bool = true| -> valid:
            if alphabet[j] != j:
                valid <- false
                break
    ordered: bool = selected.len.i64() >= 16 and width >= 16 and not indexed and ordered_alphabet(alphabet)
    lookup: darray[i64] = alphabet_columns(alphabet, width) if selected.len.i64() >= 16 and width >= 16 and not indexed and not ordered else []
    state, total, failed =
        for k in 0..<selected.len.i64() |state: i64 = start, total: f64 = 0.0, failed: bool = false| -> (state, total, failed):
            symbol: i64 = selected[k]
            column: i64 =
                if indexed:
                    symbol if symbol >= 0 and symbol < width else -1
                elif lookup.count > 0 and symbol >= 0 and symbol < width:
                    lookup[symbol]
                elif ordered:
                    ordered_column(alphabet, symbol, true)
                else:
                    for j in 0..<width |found: i64 = -1| -> found:
                        if alphabet[j] == symbol:
                            found <- j
                            break
            return log(0.0) if column < 0
            edge: i64 = state * width + column
            target: i64 = transitions[edge]
            return log(0.0) if target < 0
            return log(0.0) if weights[edge] == log(0.0)
            if not failed:
                value: f64 = total + weights[edge]
                if value > -67108864.0 and value < 67108864.0:
                    total <- value
                else:
                    checked: f64 = partition_log_product(total, weights[edge])
                    if checked != checked:
                        failed <- true
                    else:
                        total <- checked
            state <- target
    return log(0.0) if final[state] == log(0.0)
    return log(-1.0) if failed
    return partition_log_product(total, final[state])

def log_add_present(x: f64, y: f64) -> f64:
    return x + log1p(exp(y - x)) if x >= y else y + log1p(exp(x - y))

# Stable log-sum, including unreachable states.
def log_add(x: f64, y: f64) -> f64:
    return y if x == log(0.0)
    return x if y == log(0.0)
    return log_add_present(x, y)

# Detect a distorted log-sum correction at the posterior normalization tolerance.
def partition_log_add(x: f64, y: f64) -> f64:
    return y if x == log(0.0)
    return x if y == log(0.0)
    larger: f64 = x if x >= y else y
    smaller: f64 = y if x >= y else x
    correction: f64 = log1p(exp(smaller - larger))
    result: f64 = larger + correction
    # Below 2^26, binary64 round-to-nearest error is less than 2^-27.
    return result if result > -67108864.0 and result < 67108864.0
    roundoff: f64 = (result - larger) - correction
    return log(-1.0) if roundoff >= 1.01e-8 or roundoff <= -1.01e-8
    return result

# TwoSum recovers the rounding residual of a finite log-weight addition.
def partition_log_product(x: f64, y: f64) -> f64:
    result: f64 = x + y
    return log(-1.0) if result == log(0.0) or result == -log(0.0) or result != result
    return result if result > -67108864.0 and result < 67108864.0
    virtual: f64 = result - x
    residual: f64 = (x - (result - virtual)) + (y - virtual)
    return log(-1.0) if residual != residual or residual >= 1.01e-8 or residual <= -1.01e-8
    return result

# Construct checked tilted edges: 0 success, 1 overflow, 2 precision loss, 3 shape error.
def tilt_weights_checked(weights: view[f64], factors: view[f64], output: mutable view[f64]) -> i64 can[Abort.Panic]:
    width: i64 = factors.len.i64()
    return 3 if width == 0 or weights.len.i64() != output.len.i64()
    return 3 if weights.len.i64() % width != 0
    for state in 0..<(weights.len.i64() / width):
        for symbol in 0..<width:
            index: i64 = state * width + symbol
            weight: f64 = weights[index]
            if weight == log(0.0):
                output[index] <- weight
            else:
                value: f64 = weight + factors[symbol]
                return 1 if value == log(0.0) or value == -log(0.0) or value != value
                if value <= -67108864.0 or value >= 67108864.0:
                    virtual: f64 = value - weight
                    residual: f64 = (weight - (value - virtual)) + (factors[symbol] - virtual)
                    return 2 if residual != residual or residual >= 1.01e-8 or residual <= -1.01e-8
                output[index] <- value
    return 0

# Sum off-reference masses and log(max(1, row mass)) without cancellation.
def tail_mass_summary(log_probs: view[f64], reference: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = reference.len.i64()
    return [log(0.0), 0.0] if m == 0
    width: i64 = log_probs.len.i64() / m
    total, scale, _ =
        for k in 0..<m |total: f64 = log(0.0), scale: f64 = 0.0, correction: f64 = 0.0| -> (total, scale, correction):
            row, next_total =
                for j in 0..<width |row: f64 = log(0.0), off: f64 = total| -> (row, off):
                    reading: f64 = log_probs[k * width + j]
                    row <- log_add(row, reading)
                    off <- log_add(off, reading) if j != reference[k] else off
            total <- next_total
            excess: f64 = row if row > 0.0 else 0.0
            adjusted: f64 = excess - correction
            next: f64 = scale + adjusted
            correction <- (next - scale) - adjusted
            scale <- next
    return [total, scale]

# Refresh one block, or every block for index -1, then combine their summaries.
# The caller owns a pair of f64 values per block: log off-mass and log scale.
def tail_block_summary(log_probs: view[f64], reference: view[i64], blocks: mutable view[f64], block_size: i64, index: i64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = reference.len.i64()
    return [] if m == 0 or block_size <= 0 or index < -1 or index >= m
    return [] if log_probs.len.i64() % m != 0
    width: i64 = log_probs.len.i64() / m
    return [] if width == 0
    count: i64 = (m - 1) / block_size + 1
    return [] if blocks.len.i64() / 2 != count or blocks.len.i64() % 2 != 0
    first: i64 = 0 if index == -1 else index / block_size
    end: i64 = count if index == -1 else first + 1
    for b in first..<end:
        start: i64 = b * block_size
        remaining: i64 = m - start
        stop: i64 = start + (block_size if block_size < remaining else remaining)
        for k in start..<stop:
            return [] if reference[k] < 0 or reference[k] >= width
        off, block_scale, _ =
            for k in start..<stop |off: f64 = log(0.0), block_scale: f64 = 0.0, block_correction: f64 = 0.0| -> (off, block_scale, block_correction):
                peak, peak_index =
                    for j in 0..<width |peak: f64 = log(0.0), peak_index: i64 = -1| -> (peak, peak_index):
                        reading: f64 = log_probs[k * width + j]
                        if j != reference[k] and reading > peak:
                            peak <- reading
                            peak_index <- j
                last: i64 = width if peak_index >= 0 else 0
                rest, _ =
                    for j in 0..<last |rest: f64 = 0.0, correction: f64 = 0.0| -> (rest, correction):
                        reading: f64 = log_probs[k * width + j]
                        if j != reference[k] and j != peak_index and reading != log(0.0):
                            adjusted: f64 = exp(reading - peak) - correction
                            next: f64 = rest + adjusted
                            correction <- (next - rest) - adjusted
                            rest <- next
                row_off: f64 = peak + log1p(rest) if peak_index >= 0 else peak
                row: f64 = log_add(log_probs[k * width + reference[k]], row_off)
                off <- log_add(off, row_off)
                excess: f64 = row if row > 0.0 else 0.0
                adjusted: f64 = excess - block_correction
                next: f64 = block_scale + adjusted
                block_correction <- (next - block_scale) - adjusted
                block_scale <- next
        blocks[b * 2] <- off
        blocks[b * 2 + 1] <- block_scale
    total, scale, _ =
        for b in 0..<count |total: f64 = log(0.0), scale: f64 = 0.0, correction: f64 = 0.0| -> (total, scale, correction):
            total <- log_add(total, blocks[b * 2])
            adjusted: f64 = blocks[b * 2 + 1] - correction
            next: f64 = scale + adjusted
            correction <- (next - scale) - adjusted
            scale <- next
    return [total, scale]

# Search only through the number of positions; beyond it the tail is empty.
def initial_band_changes_scaled(log_off: f64, log_factor: f64, log_slack: f64, length: i64) -> i64:
    # Reserve a representable sentinel for a tail beyond the final position.
    return -1 if length < 0 or length == 9223372036854775807
    return 1 if log_off == log(0.0)
    return 1 if length == 0
    first: f64 = log_off + log_factor
    return -1 if first == log(0.0) or first == -log(0.0) or first != first
    return 1 if first <= log_slack
    # Above a threshold below one, C*S^j/j! is first increasing and then
    # decreasing. Since j=1 failed, its qualifying indices form a suffix.
    for _ in 0..<64 |low: i64 = 1, high: i64 = length + 1|:
        return high if high - low <= 1
        j: i64 = low + (high - low) / 2
        estimate: f64 = j.f64() * log_off - lgamma((j + 1).f64()) + log_factor
        return -1 if estimate == log(0.0) or estimate == -log(0.0) or estimate != estimate
        high <- j if estimate <= log_slack else high
        low <- j if estimate > log_slack else low
    return length + 1

# Separate the selected format path from all different accepted paths.
def format_partition(log_probs: view[f64], alphabet: view[i64], selected: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = selected.len.i64()
    count: i64 = alphabet.len.i64()
    return [] if not matrix_shape(log_probs.len.i64(), m, count)
    width: i64 = m + 2
    missing: f64 = log(0.0)
    for j in 0..<count:
        return [] if alphabet[j] < 0
    alternatives: darray[f64] = [missing for _ in 0..<(2 * width)]
    matched: darray[f64] = [0.0]
    state: darray[i64] = [1]
    active: mutable darray[i64] = [0 for _ in 0..<count]
    bounds: darray[i64] = [width, -1, width, -1]
    for k in 0..<m:
        here_bound: i64 = (k % 2) * 2
        next_bound: i64 = ((k + 1) % 2) * 2
        return [missing, missing] if matched[0] == missing and bounds[here_bound] > bounds[here_bound + 1]
        active_count: i64 =
            for j in 0..<count |found: i64 = 0, active| -> found:
                if log_probs[k * count + j] != missing and alphabet[j] <= m - k - 1:
                    active[found] <- j
                    found += 1
        return [missing, missing] if active_count == 0
        here: i64 = (k % 2) * width
        next: i64 = ((k + 1) % 2) * width
        for n in bounds[next_bound]..<(bounds[next_bound + 1] + 1):
            alternatives[next + n] <- missing
        bounds[next_bound] <- width
        bounds[next_bound + 1] <- -1
        first: i64 = state[0] if matched[0] != missing and state[0] >= 1 and state[0] <= m - k and state[0] < bounds[here_bound] else bounds[here_bound]
        last: i64 = state[0] if matched[0] != missing and state[0] >= 1 and state[0] <= m - k and state[0] > bounds[here_bound + 1] else bounds[here_bound + 1]
        low: i64 = 1 if first < 1 else first
        high: i64 = m - k if last > m - k else last
        matched_state: i64 = state[0] if matched[0] != missing else -1
        for n in low..<(high + 1):
            source: f64 = alternatives[here + n]
            same: bool = n == matched_state
            continue if source == missing and not same
            for position in 0..<active_count:
                j: i64 = active[position]
                arity: i64 = alphabet[j]
                target: i64 = n - 1 + arity
                continue if target > m - k - 1
                reading: f64 = log_probs[k * count + j]
                if source != missing:
                    through: f64 = partition_log_product(source, reading)
                    return [] if through == missing or through == -missing or through != through
                    combined: f64 = partition_log_add(alternatives[next + target], through)
                    return [] if combined != combined
                    alternatives[next + target] <- combined
                    bounds[next_bound] <- target if target < bounds[next_bound] else bounds[next_bound]
                    bounds[next_bound + 1] <- target if target > bounds[next_bound + 1] else bounds[next_bound + 1]
                if same and arity != selected[k]:
                    through: f64 = partition_log_product(matched[0], reading)
                    return [] if through == missing or through == -missing or through != through
                    combined: f64 = partition_log_add(alternatives[next + target], through)
                    return [] if combined != combined
                    alternatives[next + target] <- combined
                    bounds[next_bound] <- target if target < bounds[next_bound] else bounds[next_bound]
                    bounds[next_bound + 1] <- target if target > bounds[next_bound + 1] else bounds[next_bound + 1]
        chosen: i64 =
            for j in 0..<count |found: i64 = -1| -> found:
                if alphabet[j] == selected[k]:
                    found <- j
                    break
        if chosen < 0 or selected[k] < 0 or selected[k] > m - k - 1 or state[0] < 1:
            matched[0] <- missing
        else:
            state[0] <- state[0] - 1 + selected[k]
            reading: f64 = log_probs[k * count + chosen]
            if state[0] > m - k - 1 or matched[0] == missing or reading == missing:
                matched[0] <- missing
            else:
                value: f64 = partition_log_product(matched[0], reading)
                return [] if value == missing or value == -missing or value != value
                matched[0] <- value
    return [matched[0] if state[0] == 0 else missing, alternatives[(m % 2) * width]]

# Exact format decoding in log space, used when linear-space paths underflow.
def decode_log(log_probs: view[f64], alphabet: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    alphabet_size: i64 = alphabet.len.i64()
    return [] if alphabet_size == 0 or log_probs.len.i64() % alphabet_size != 0
    m: i64 = log_probs.len.i64() / alphabet_size
    return [] if m == 0
    max_arity: i64 =
        for j in 0..<alphabet_size |largest: i64 = 0| -> largest:
            return [] if alphabet[j] < 0
            largest <- alphabet[j] if alphabet[j] > largest and alphabet[j] < m else largest
    offsets: darray[i64] =
        for k in 0..<(m + 1) |offsets: darray[i64] = [0 for _ in 0..<(m + 2)]| -> offsets:
            offsets[k + 1] <- offsets[k] + live(k, m, max_arity) + 1
    width: i64 = m + 2
    unreachable: f64 = log(0.0)
    completable: darray[bool] = [i == offsets[m] for i in 0..<offsets[m + 1]]
    for step in 0..<m:
        k: i64 = m - 1 - step
        here_top: i64 = live(k, m, max_arity)
        next_top: i64 = live(k + 1, m, max_arity)
        for j in 0..<alphabet_size:
            arity: i64 = alphabet[j]
            continue if arity > next_top or log_probs[k * alphabet_size + j] == unreachable
            limit: i64 = next_top + 1 - arity
            top: i64 = limit if limit < here_top else here_top
            for state in 1..<(top + 1):
                target: i64 = state - 1 + arity
                if completable[offsets[k + 1] + target]:
                    completable[offsets[k] + state] <- true
    return [] if not completable[1]
    forward: darray[f64] = [0.0 if i == 1 else unreachable for i in 0..<offsets[m + 1]]
    best: darray[f64] = [0.0 if i == 1 else unreachable for i in 0..<(2 * width)]
    choice: darray[i64] = [0 for _ in 0..<offsets[m + 1]]
    for k in 0..<m:
        here_top: i64 = live(k, m, max_arity)
        next_top: i64 = live(k + 1, m, max_arity)
        best_source: i64 = (k % 2) * width
        best_target: i64 = ((k + 1) % 2) * width
        for state in 0..<(next_top + 1):
            best[best_target + state] <- unreachable
        for j in 0..<alphabet_size:
            arity: i64 = alphabet[j]
            continue if arity > next_top
            step: f64 = log_probs[k * alphabet_size + j]
            limit: i64 = next_top + 1 - arity
            top: i64 = limit if limit < here_top else here_top
            for state in 1..<(top + 1):
                target: i64 = state - 1 + arity
                continue if not completable[offsets[k + 1] + target]
                cell: i64 = offsets[k + 1] + target
                source: f64 = forward[offsets[k] + state]
                through: f64 = source + step
                return [log(-1.0)] if source != unreachable and step != unreachable and (through == unreachable or through == -unreachable or through != through)
                forward[cell] <- log_add(forward[cell], through)
                candidate: f64 = best[best_source + state] + step
                return [log(-1.0)] if best[best_source + state] != unreachable and step != unreachable and (candidate == unreachable or candidate == -unreachable or candidate != candidate)
                if candidate > best[best_target + target]:
                    best[best_target + target] <- candidate
                    choice[cell] <- j
    log_z: f64 = forward[offsets[m]]
    return [] if log_z == unreachable
    result: darray[f64] = [0.0 for _ in 0..<(1 + m + m * alphabet_size)]
    result[0] <- log_z
    trace: darray[i64] = [0]
    for step in 0..<m:
        k: i64 = m - step
        arity: i64 = alphabet[choice[offsets[k] + trace[0]]]
        result[k] <- arity.f64()
        trace[0] <- trace[0] + 1 - arity
    backward: mutable darray[f64] = [0.0 if i == (m % 2) * width else unreachable for i in 0..<(2 * width)]
    for step in 0..<m:
        k: i64 = m - 1 - step
        here_top: i64 = live(k, m, max_arity)
        next_top: i64 = live(k + 1, m, max_arity)
        backward_here: i64 = (k % 2) * width
        backward_next: i64 = ((k + 1) % 2) * width
        for state in 0..<(here_top + 1):
            backward[backward_here + state] <- unreachable
        for j in 0..<alphabet_size:
            arity: i64 = alphabet[j]
            continue if arity > next_top
            reading: f64 = log_probs[k * alphabet_size + j]
            limit: i64 = next_top + 1 - arity
            top: i64 = limit if limit < here_top else here_top
            marginal: f64 =
                for state in 1..<(top + 1) |backward, total: f64 = unreachable| -> total:
                    target: i64 = state - 1 + arity
                    source: f64 = forward[offsets[k] + state]
                    continue if source == unreachable
                    suffix: f64 = backward[backward_next + target]
                    through: f64 = reading + suffix
                    return [log(-1.0)] if reading != unreachable and suffix != unreachable and (through == unreachable or through == -unreachable or through != through)
                    backward[backward_here + state] <- log_add(backward[backward_here + state], through)
                    weighted: f64 = source + through
                    return [log(-1.0)] if source != unreachable and through != unreachable and (weighted == unreachable or weighted == -unreachable or weighted != weighted)
                    total <- log_add(total, weighted)
            result[1 + m + k * alphabet_size + j] <- exp(marginal - log_z)
    return result

# Sum-product only, retaining two state rows; no maximum or marginal tables.
