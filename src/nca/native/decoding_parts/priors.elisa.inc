def prior_normalizer(log_probs: view[f64], alphabet: view[i64], transitions: view[i64], prior: view[f64], final: view[f64], start: i64) -> f64 can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    states: i64 = final.len.i64()
    m: i64 = log_probs.len.i64() / width
    unreachable: f64 = log(0.0)
    return final[start] if m == 0
    rows, bounds =
        for k in 0..<m |rows: darray[f64] = [0.0 if i == start else unreachable for i in 0..<(2 * states)], bounds: darray[i64] = [start, start, 0, -1], active: darray[i64] = [0 for _ in 0..<width]| -> (rows, bounds):
            here_bound: i64 = (k % 2) * 2
            return unreachable if bounds[here_bound] > bounds[here_bound + 1]
            count: i64 =
                for j in 0..<width |count: i64 = 0, active| -> count:
                    if log_probs[k * width + j] != unreachable:
                        active[count] <- j
                        count += 1
            return unreachable if count == 0
            here: i64 = (k % 2) * states
            next: i64 = ((k + 1) % 2) * states
            next_bound: i64 = ((k + 1) % 2) * 2
            # Every cell outside the old destination envelope is already unreachable.
            for state in bounds[next_bound]..<(bounds[next_bound + 1] + 1) |rows|:
                rows[next + state] <- unreachable
            bounds[next_bound] <- states
            bounds[next_bound + 1] <- -1
            for state in bounds[here_bound]..<(bounds[here_bound + 1] + 1) |rows, bounds|:
                continue if rows[here + state] == unreachable
                for position in 0..<count |rows, bounds|:
                    j: i64 = active[position]
                    edge: i64 = state * width + j
                    target: i64 = transitions[edge]
                    continue if target < 0
                    reading: f64 = log_probs[k * width + j]
                    edge_weight: f64 = prior[edge]
                    continue if edge_weight == unreachable
                    weight: f64 = reading + edge_weight
                    return log(-1.0) if weight == unreachable or weight == -unreachable
                    through: f64 = rows[here + state] + weight
                    return log(-1.0) if through == unreachable or through == -unreachable
                    existing: f64 = rows[next + target]
                    rows[next + target] <- through if existing == unreachable else log_add_present(existing, through)
                    bounds[next_bound] <- target if target < bounds[next_bound] else bounds[next_bound]
                    bounds[next_bound + 1] <- target if target > bounds[next_bound + 1] else bounds[next_bound + 1]
    return
        for state in bounds[(m % 2) * 2]..<(bounds[(m % 2) * 2 + 1] + 1) |total: f64 = unreachable| -> total:
            last: f64 = rows[(m % 2) * states + state]
            continue if last == unreachable or final[state] == unreachable
            weighted: f64 = last + final[state]
            return log(-1.0) if weighted == unreachable or weighted == -unreachable
            total <- log_add(total, weighted)

# Sum the selected path and every different path separately. Empty output
# signals finite arithmetic overflow; -inf denotes absent mass.
def prior_partition(log_probs: view[f64], alphabet: view[i64], transitions: view[i64], prior: view[f64], final: view[f64], start: i64, selected: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    states: i64 = final.len.i64()
    m: i64 = selected.len.i64()
    unreachable: f64 = log(0.0)
    indexed: bool = m >= 16 and indexed_alphabet(alphabet)
    ordered: bool = m >= 16 and width >= 16 and not indexed and ordered_alphabet(alphabet)
    lookup: darray[i64] = alphabet_columns(alphabet, width) if m >= 16 and width >= 16 and not indexed and not ordered else []
    rows, bounds, matched_state, matched =
        for k in 0..<m |rows: darray[f64] = [unreachable for _ in 0..<(2 * states)], bounds: darray[i64] = [states, -1, states, -1], matched_state: i64 = start, matched: f64 = 0.0, active: darray[i64] = [0 for _ in 0..<width]| -> (rows, bounds, matched_state, matched):
            here: i64 = (k % 2) * states
            next: i64 = ((k + 1) % 2) * states
            here_bound: i64 = (k % 2) * 2
            next_bound: i64 = ((k + 1) % 2) * 2
            return [unreachable, unreachable] if matched == unreachable and bounds[here_bound] > bounds[here_bound + 1]
            active_count: i64 =
                for j in 0..<width |count: i64 = 0, active| -> count:
                    if log_probs[k * width + j] != unreachable:
                        active[count] <- j
                        count += 1
            return [unreachable, unreachable] if active_count == 0
            for state in bounds[next_bound]..<(bounds[next_bound + 1] + 1) |rows|:
                rows[next + state] <- unreachable
            bounds[next_bound] <- states
            bounds[next_bound + 1] <- -1
            low: i64 = matched_state if matched != unreachable and matched_state < bounds[here_bound] else bounds[here_bound]
            high: i64 = matched_state if matched != unreachable and matched_state > bounds[here_bound + 1] else bounds[here_bound + 1]
            for state in low..<(high + 1) |rows, bounds|:
                source: f64 = rows[here + state]
                same: bool = state == matched_state and matched != unreachable
                continue if source == unreachable and not same
                for position in 0..<active_count |rows, bounds|:
                    j: i64 = active[position]
                    edge: i64 = state * width + j
                    target: i64 = transitions[edge]
                    continue if target < 0
                    reading: f64 = log_probs[k * width + j]
                    edge_weight: f64 = prior[edge]
                    continue if edge_weight == unreachable
                    weight: f64 = partition_log_product(reading, edge_weight)
                    continue if source == unreachable and (not same or alphabet[j] == selected[k])
                    return [] if weight != weight
                    if source != unreachable:
                        through: f64 = partition_log_product(source, weight)
                        return [] if through != through
                        combined: f64 = partition_log_add(rows[next + target], through)
                        return [] if combined != combined
                        rows[next + target] <- combined
                    bounds[next_bound] <- target if target < bounds[next_bound] else bounds[next_bound]
                    bounds[next_bound + 1] <- target if target > bounds[next_bound + 1] else bounds[next_bound + 1]
                    if same and alphabet[j] != selected[k]:
                        through: f64 = partition_log_product(matched, weight)
                        return [] if through != through
                        combined: f64 = partition_log_add(rows[next + target], through)
                        return [] if combined != combined
                        rows[next + target] <- combined
            if matched != unreachable:
                chosen: i64 =
                    if indexed:
                        selected[k] if selected[k] >= 0 and selected[k] < width else -1
                    elif lookup.count > 0 and selected[k] >= 0 and selected[k] < width:
                        lookup[selected[k]]
                    elif ordered:
                        ordered_column(alphabet, selected[k], true)
                    else:
                        for j in 0..<width |chosen: i64 = -1| -> chosen:
                            if alphabet[j] == selected[k]:
                                chosen <- j
                                break
                if chosen < 0:
                    matched <- unreachable
                else:
                    edge: i64 = matched_state * width + chosen
                    target: i64 = transitions[edge]
                    reading: f64 = log_probs[k * width + chosen]
                    edge_weight: f64 = prior[edge]
                    if target < 0 or reading == unreachable or edge_weight == unreachable:
                        matched <- unreachable
                    else:
                        weight: f64 = partition_log_product(reading, edge_weight)
                        return [] if weight != weight
                        value: f64 = partition_log_product(matched, weight)
                        return [] if value != value
                        matched <- value
                        matched_state <- target
    selected_weight: f64 =
        if matched == unreachable or final[matched_state] == unreachable:
            unreachable
        else:
            value: f64 = partition_log_product(matched, final[matched_state])
            return [] if value != value
            value
    alternative: f64 =
        for state in bounds[(m % 2) * 2]..<(bounds[(m % 2) * 2 + 1] + 1) |total: f64 = unreachable| -> total:
            last: f64 = rows[(m % 2) * states + state]
            continue if last == unreachable or final[state] == unreachable
            value: f64 = partition_log_product(last, final[state])
            return [] if value != value
            combined: f64 = partition_log_add(total, value)
            return [] if combined != combined
            total <- combined
    return [selected_weight, alternative]

# Max-product and traceback only. Traversal and strict ties match decode_prior.
def prior_best(log_probs: view[f64], alphabet: view[i64], transitions: view[i64], prior: view[f64], final: view[f64], start: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    states: i64 = final.len.i64()
    m: i64 = log_probs.len.i64() / width
    unreachable: f64 = log(0.0)
    return [] if m == 0
    first_present: bool =
        for j in 0..<width |found: bool = false| -> found:
            if log_probs[j] != unreachable:
                found <- true
                break
    return [] if not first_present
    rows, choice, bounds =
        for k in 0..<m |rows: darray[f64] = [0.0 if i == start else log(0.0) for i in 0..<(2 * states)], choice: darray[i64] = [-1 for _ in 0..<((m + 1) * states)], bounds: darray[i64] = [start, start, 0, -1], active: darray[i64] = [0 for _ in 0..<width]| -> (rows, choice, bounds):
            here_bound: i64 = (k % 2) * 2
            return [] if bounds[here_bound] > bounds[here_bound + 1]
            active_count: i64 =
                for j in 0..<width |count: i64 = 0, active| -> count:
                    if log_probs[k * width + j] != unreachable:
                        active[count] <- j
                        count += 1
            return [] if active_count == 0
            here: i64 = (k % 2) * states
            next: i64 = ((k + 1) % 2) * states
            next_bound: i64 = ((k + 1) % 2) * 2
            for state in bounds[next_bound]..<(bounds[next_bound + 1] + 1) |rows|:
                rows[next + state] <- log(0.0)
            bounds[next_bound] <- states
            bounds[next_bound + 1] <- -1
            for state in bounds[here_bound]..<(bounds[here_bound + 1] + 1) |rows, choice, bounds|:
                continue if rows[here + state] == log(0.0)
                for position in 0..<active_count |rows, choice, bounds|:
                    j: i64 = active[position]
                    edge: i64 = state * width + j
                    target: i64 = transitions[edge]
                    continue if target < 0
                    reading: f64 = log_probs[k * width + j]
                    edge_weight: f64 = prior[edge]
                    continue if edge_weight == unreachable
                    weight: f64 = partition_log_product(reading, edge_weight)
                    return [] if weight != weight
                    candidate: f64 = partition_log_product(rows[here + state], weight)
                    return [] if candidate != candidate
                    if candidate > rows[next + target]:
                        rows[next + target] <- candidate
                        choice[(k + 1) * states + target] <- edge
                        bounds[next_bound] <- target if target < bounds[next_bound] else bounds[next_bound]
                        bounds[next_bound + 1] <- target if target > bounds[next_bound + 1] else bounds[next_bound + 1]
    terminal: i64 =
        for state in bounds[(m % 2) * 2]..<(bounds[(m % 2) * 2 + 1] + 1) |top: f64 = log(0.0), terminal: i64 = -1| -> terminal:
            last: f64 = rows[(m % 2) * states + state]
            continue if last == unreachable or final[state] == unreachable
            candidate: f64 = partition_log_product(last, final[state])
            return [] if candidate != candidate
            if candidate > top:
                top <- candidate
                terminal <- state
    return [] if terminal < 0
    return
        for step in 0..<m |selected: darray[i64] = [0 for _ in 0..<m], state: i64 = terminal| -> selected:
            edge: i64 = choice[(m - step) * states + state]
            selected[m - step - 1] <- alphabet[edge % width]
            state <- edge / width

# A typed Python result; absence is represented by null, not an empty packed array.
struct PriorDecoded:
    log_z: f64
    arities: darray[i64]
    marginals: darray[darray[f64]]

# A conservative magnitude envelope for every forward, backward and split sum.
def prior_small_arithmetic(log_probs: view[f64], prior: view[f64], final: view[f64], width: i64) -> bool:
    m: i64 = log_probs.len.i64() / width
    unreachable: f64 = log(0.0)
    reading_bound: f64 =
        for k in 0..<m |total: f64 = 0.0| -> total:
            peak: f64 =
                for j in 0..<width |peak: f64 = 0.0| -> peak:
                    value: f64 = log_probs[k * width + j]
                    continue if value == unreachable
                    magnitude: f64 = -value if value < 0.0 else value
                    peak <- magnitude if magnitude > peak else peak
            total += peak
    edge_bound: f64 =
        for i in 0..<prior.len.i64() |peak: f64 = 0.0| -> peak:
            value: f64 = prior[i]
            continue if value == unreachable
            magnitude: f64 = -value if value < 0.0 else value
            peak <- magnitude if magnitude > peak else peak
    final_bound: f64 =
        for i in 0..<final.len.i64() |peak: f64 = 0.0| -> peak:
            value: f64 = final[i]
            continue if value == unreachable
            magnitude: f64 = -value if value < 0.0 else value
            peak <- magnitude if magnitude > peak else peak
    bound: f64 = reading_bound + m.f64() * (edge_bound + log(width.f64())) + final_bound
    # The extra factor of four leaves room for split subtraction and rounding.
    return bound < 16777216.0

# Weighted deterministic prior automaton (§27), including any format restriction.
# Caller validates dimensions and state indices; -1 denotes a forbidden transition.
def decode_prior(log_probs: view[f64], alphabet: view[i64], transitions: view[i64], prior: view[f64], final: view[f64], start: i64) -> PriorDecoded? can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    states: i64 = final.len.i64()
    m: i64 = log_probs.len.i64() / width
    unreachable: f64 = log(0.0)
    if m == 0:
        return null if final[start] == unreachable
        return PriorDecoded{log_z: final[start], arities: [], marginals: []}
    first_present: bool =
        for j in 0..<width |found: bool = false| -> found:
            if log_probs[j] != unreachable:
                found <- true
                break
    return null if not first_present
    small: bool = prior_small_arithmetic(log_probs, prior, final, width)
    forward, best, choice, bounds =
        for k in 0..<m |forward: darray[f64] = [0.0 if i == start else log(0.0) for i in 0..<((m + 1) * states)], best: darray[f64] = [0.0 if i == start else log(0.0) for i in 0..<(2 * states)], choice: darray[i64] = [-1 for _ in 0..<((m + 1) * states)], bounds: darray[i64] = [start if i < 2 else (states if i % 2 == 0 else -1) for i in 0..<(2 * (m + 1))], active: darray[i64] = [0 for _ in 0..<width]| -> (forward, best, choice, bounds):
            return null if bounds[2 * k] > bounds[2 * k + 1]
            active_count: i64 =
                for j in 0..<width |count: i64 = 0, active| -> count:
                    if log_probs[k * width + j] != unreachable:
                        active[count] <- j
                        count += 1
            return null if active_count == 0
            here: i64 = (k % 2) * states
            next: i64 = ((k + 1) % 2) * states
            # The destination row was last used at position k - 1.
            if k > 0:
                for state in bounds[2 * (k - 1)]..<(bounds[2 * (k - 1) + 1] + 1) |best|:
                    best[next + state] <- unreachable
            for state in bounds[2 * k]..<(bounds[2 * k + 1] + 1) |forward, best, choice, bounds|:
                continue if forward[k * states + state] == log(0.0)
                for position in 0..<active_count |forward, best, choice, bounds|:
                    j: i64 = active[position]
                    edge: i64 = state * width + j
                    target: i64 = transitions[edge]
                    continue if target < 0
                    cell: i64 = (k + 1) * states + target
                    reading: f64 = log_probs[k * width + j]
                    edge_weight: f64 = prior[edge]
                    continue if edge_weight == unreachable
                    weight: f64 = reading + edge_weight if small else partition_log_product(reading, edge_weight)
                    return null if weight != weight
                    through: f64 = forward[k * states + state] + weight if small else partition_log_product(forward[k * states + state], weight)
                    return null if through != through
                    combined: f64 = log_add(forward[cell], through) if small else partition_log_add(forward[cell], through)
                    return null if combined != combined
                    forward[cell] <- combined
                    if target < bounds[2 * (k + 1)]:
                        bounds[2 * (k + 1)] <- target
                    if target > bounds[2 * (k + 1) + 1]:
                        bounds[2 * (k + 1) + 1] <- target
                    candidate: f64 = best[here + state] + weight if small else partition_log_product(best[here + state], weight)
                    return null if candidate != candidate
                    if candidate > best[next + target]:
                        best[next + target] <- candidate
                        choice[cell] <- edge
    log_z, terminal =
        for state in bounds[2 * m]..<(bounds[2 * m + 1] + 1) |log_z: f64 = log(0.0), top: f64 = log(0.0), terminal: i64 = -1| -> (log_z, terminal):
            continue if forward[m * states + state] == unreachable or final[state] == unreachable
            weighted: f64 = forward[m * states + state] + final[state] if small else partition_log_product(forward[m * states + state], final[state])
            return null if weighted != weighted
            combined: f64 = log_add(log_z, weighted) if small else partition_log_add(log_z, weighted)
            return null if combined != combined
            log_z <- combined
            candidate: f64 = best[(m % 2) * states + state] + final[state] if small else partition_log_product(best[(m % 2) * states + state], final[state])
            return null if candidate != candidate
            if candidate > top:
                top <- candidate
                terminal <- state
    return null if terminal < 0
    decoded: darray[i64] =
        for step in 0..<m |decoded: darray[i64] = [0 for _ in 0..<m], state: i64 = terminal| -> decoded:
            edge: i64 = choice[(m - step) * states + state]
            decoded[m - step - 1] <- alphabet[edge % width]
            state <- edge / width
    marginals: darray[darray[f64]] =
        for step in 0..<m |result: darray[darray[f64]] = [[0.0 for _ in 0..<width] for _ in 0..<m], backward: darray[f64] = [final[i % states] if i / states == m % 2 and forward[m * states + i % states] != unreachable else unreachable for i in 0..<(2 * states)], active: darray[i64] = [0 for _ in 0..<width]| -> result:
            k: i64 = m - 1 - step
            active_count: i64 =
                for j in 0..<width |count: i64 = 0, active| -> count:
                    if log_probs[k * width + j] != unreachable:
                        active[count] <- j
                        count += 1
            here: i64 = (k % 2) * states
            next: i64 = ((k + 1) % 2) * states
            # The reused row contains only support from position k + 2.
            if k + 2 <= m:
                for state in bounds[2 * (k + 2)]..<(bounds[2 * (k + 2) + 1] + 1) |backward|:
                    backward[here + state] <- unreachable
            for state in bounds[2 * k]..<(bounds[2 * k + 1] + 1) |backward, result|:
                continue if forward[k * states + state] == log(0.0)
                for position in 0..<active_count |backward, result|:
                    j: i64 = active[position]
                    edge: i64 = state * width + j
                    target: i64 = transitions[edge]
                    continue if target < 0
                    reading: f64 = log_probs[k * width + j]
                    edge_weight: f64 = prior[edge]
                    suffix: f64 = backward[next + target]
                    continue if edge_weight == unreachable or suffix == unreachable
                    weight: f64 = reading + edge_weight if small else partition_log_product(reading, edge_weight)
                    return null if weight != weight
                    through: f64 = weight + suffix if small else partition_log_product(weight, suffix)
                    return null if through != through
                    combined: f64 = log_add(backward[here + state], through) if small else partition_log_add(backward[here + state], through)
                    return null if combined != combined
                    backward[here + state] <- combined
                    first: f64 = forward[k * states + state] + reading if small else partition_log_product(forward[k * states + state], reading)
                    return null if first != first
                    second: f64 = first + edge_weight if small else partition_log_product(first, edge_weight)
                    return null if second != second
                    third: f64 = second + suffix if small else partition_log_product(second, suffix)
                    return null if third != third
                    exponent: f64 = third - log_z if small else partition_log_product(third, -log_z)
                    return null if exponent != exponent
                    result[k][j] <- result[k][j] + exp(exponent)
    return PriorDecoded{log_z: log_z, arities: decoded, marginals: marginals}

# The banded cursor of THEORY §23.4. The caller owns the tables, `width`
# states per row, and keeps rows current around a cursor; these functions recompute rows in
# place. Row `k` holds states `low[k] ..= high[k]`. Both sum and max tables hold log weights.

# For arity `a` at position `i`: the first in-band state `s ≥ 1` whose successor `s − 1 + a` is
# in band at `i + 1`, and how many consecutive such states there are.
