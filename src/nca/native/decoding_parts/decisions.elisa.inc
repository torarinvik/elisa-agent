def grouped_masses(scores: view[f64], groups: view[i64], entries: i64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = groups.len.i64()
    m: i64 = scores.len.i64() / width
    result, correction =
        for k in 0..<m |result: darray[f64] = [0.0 for _ in 0..<(m * entries)], correction: darray[f64] = [0.0 for _ in 0..<(m * entries)]| -> (result, correction):
            for c in 0..<width |result, correction|:
                cell: i64 = k * entries + groups[c]
                previous: f64 = result[cell]
                weight: f64 = scores[k * width + c]
                total: f64 = previous + weight
                correction[cell] <- correction[cell] + ((previous - total) + weight if previous >= weight else (weight - total) + previous)
                result[cell] <- total
    return [result[i] + correction[i] for i in 0..<(m * entries)]

# Expand a validated partition's group sizes into per-class group IDs.
def partition_group_ids(lengths: view[i64], size: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    return [] if size < 0
    remaining: i64 =
        for group in 0..<lengths.len.i64() |remaining: i64 = size| -> remaining:
            length: i64 = lengths[group]
            return [] if length <= 0 or length > remaining
            remaining <- remaining - length
    return [] if remaining != 0
    result: darray[i64] = [0 for _ in 0..<size]
    offset: darray[i64] = [0]
    for group in 0..<lengths.len.i64():
        length: i64 = lengths[group]
        for i in offset[0]..<(offset[0] + length):
            result[i] <- group
        offset[0] <- offset[0] + length
    return result

# First maximum among finite, nonnegative weights; -1 signals invalid input.
def ranked_argmax_checked(weights: view[f64]) -> i64 can[Abort.Panic]:
    return -1 if weights.len.i64() == 0
    return
        for i in 0..<weights.len.i64() |top: i64 = 0| -> top:
            value: f64 = weights[i]
            return -1 if value != value or value < 0.0 or value == -log(0.0)
            top <- i if value > weights[top] else top

# Return the first maximum at caller-supplied indices; negative results report
# invalid indices (-1) or invalid selected weights (-2).
def ranked_argmax_indices_checked(weights: view[f64], indices: view[i64]) -> i64 can[Abort.Panic]:
    return -1 if indices.len.i64() == 0
    for i in 0..<indices.len.i64():
        return -1 if indices[i] < 0 or indices[i] >= weights.len.i64()
    best, top =
        for i in 0..<indices.len.i64() |best: f64 = 0.0, top: i64 = -1| -> (best, top):
            index: i64 = indices[i]
            value: f64 = weights[index]
            return -2 if value != value or value < 0.0 or value == -log(0.0)
            if top < 0 or value > best:
                best <- value
                top <- index
    return top

# First maximum in each row, matching NumPy's first-NaN behavior as well.
def row_argmax(scores: view[f64], width: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    return [] if width <= 0 or scores.len.i64() % width != 0
    return
        for k in 0..<(scores.len.i64() / width) |result: darray[i64] = [0 for _ in 0..<(scores.len.i64() / width)]| -> result:
            top: i64 =
                for c in 1..<width |top: i64 = 0| -> top:
                    old: f64 = scores[k * width + top]
                    value: f64 = scores[k * width + c]
                    top <- c if old == old and (value != value or value > old) else top
            result[k] <- top

# Argmax within each row's declared group. Strict comparison keeps the first
# class on ties. Group ids are supplied by the caller, not tied to a vocabulary.
def grouped_argmax(scores: view[f64], groups: view[i64], decisions: view[i64]) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = groups.len.i64()
    return
        for k in 0..<decisions.len.i64() |result: darray[i64] = [-1 for _ in 0..<decisions.len.i64()]| -> result:
            result[k] <-
                for c in 0..<width |chosen: i64 = -1, best: f64 = log(0.0)| -> chosen:
                    continue if groups[c] != decisions[k]
                    if chosen < 0 or scores[k * width + c] > best:
                        chosen <- c
                        best <- scores[k * width + c]

# Validate priorities and allocate risk (23.11).
# Rescale before summing and compensate additions to preserve small weights.
def risk_shares_covering(bound: f64, priorities: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    m: i64 = priorities.len.i64()
    scale: f64 =
        for k in 0..<m |largest: f64 = 0.0| -> largest:
            value: f64 = priorities[k]
            return [] if value < 0.0 or value != value or value == -log(0.0)
            largest <- value if value > largest else largest
    weights: darray[f64] = [priorities[k] / scale if scale > 0.0 else 1.0 for k in 0..<m]
    total: f64 =
        for k in 0..<m |total: f64 = 0.0, correction: f64 = 0.0| -> total:
            adjusted: f64 = weights[k] - correction
            next: f64 = total + adjusted
            correction <- (next - total) - adjusted
            total <- next
    result: darray[f64] = [bound * (weights[k] / total) for k in 0..<m]
    positive: bool =
        for k in 0..<m |found: bool = false| -> found:
            found <- true if result[k] > 0.0 else found
    if bound > 0.0 and m > 0 and not positive:
        top: i64 =
            for k in 1..<m |top: i64 = 0| -> top:
                top <- k if weights[k] > weights[top] else top
        result[top] <- bound
    if bound > 0.0 and m > 0:
        total, correction, top =
            for k in 0..<m |total: f64 = 0.0, correction: f64 = 0.0, top: i64 = 0| -> (total, correction, top):
                if result[k] > 0.0:
                    next: f64 = total + result[k]
                    return result if next == -log(0.0)
                    virtual: f64 = next - total
                    residual: f64 = (total - (next - virtual)) + (result[k] - virtual)
                    correction <- nextafter(correction + residual, log(0.0)) if residual != 0.0 else correction
                    total <- next
                top <- k if result[k] > result[top] else top
        estimate: f64 = total + correction
        lower: f64 = nextafter(estimate, 0.0) if estimate > 0.0 else 0.0
        if result[top] < bound and lower < bound:
            deficit: f64 = nextafter(bound - lower, -log(0.0))
            increased: f64 = result[top] + deficit
            result[top] <- bound if increased >= bound else nextafter(increased, -log(0.0))
    return result

# Compatibility entry points for earlier clients.
def risk_shares_checked(bound: f64, priorities: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return risk_shares_covering(bound, priorities)

def risk_shares(bound: f64, priorities: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return risk_shares_covering(bound, priorities)

# Check whether an alphabet's symbols equal their column indices.
def indexed_alphabet(alphabet: view[i64]) -> bool can[Abort.Panic]:
    return
        for c in 0..<alphabet.len.i64() |valid: bool = true| -> valid:
            if alphabet[c] != c:
                valid <- false
                break

# Nondecreasing alphabets admit binary search, including duplicate symbols.
def ordered_alphabet(alphabet: view[i64]) -> bool can[Abort.Panic]:
    for c in 1..<alphabet.len.i64():
        return false if alphabet[c - 1] > alphabet[c]
    return true

def ordered_column(alphabet: view[i64], symbol: i64, first: bool) -> i64 can[Abort.Panic]:
    low: mutable i64 = 0
    high: mutable i64 = alphabet.len.i64()
    while low < high:
        middle: i64 = low + (high - low) / 2
        value: i64 = alphabet[middle]
        return middle if value == symbol and not first
        if value < symbol:
            low <- middle + 1
        else:
            high <- middle
    return low if low < alphabet.len.i64() and alphabet[low] == symbol else -1

# Map in-range symbols to their first column; other symbols remain unindexed.
def alphabet_columns(alphabet: view[i64], limit: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    columns: darray[i64] = [-1 for _ in 0..<limit]
    for c in 0..<alphabet.len.i64():
        symbol: i64 = alphabet[c]
        if symbol >= 0 and symbol < limit and columns[symbol] < 0:
            columns[symbol] <- c
    return columns

# Test support without imposing a fixed range on alphabet symbols.
def symbols_in_alphabet(alphabet: view[i64], selected: view[i64]) -> bool can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    return true if selected.len.i64() == 0
    indexed: bool = selected.len.i64() >= 16 and indexed_alphabet(alphabet)
    ordered: bool = selected.len.i64() >= 16 and width >= 16 and not indexed and ordered_alphabet(alphabet)
    lookup: darray[i64] = alphabet_columns(alphabet, width) if selected.len.i64() >= 16 and width >= 16 and not indexed and not ordered else []
    for k in 0..<selected.len.i64():
        symbol: i64 = selected[k]
        present: bool =
            if indexed:
                symbol >= 0 and symbol < width
            elif ordered:
                ordered_column(alphabet, symbol, false) >= 0
            elif lookup.count > 0 and symbol >= 0 and symbol < width:
                lookup[symbol] >= 0
            else:
                for j in 0..<width |found: bool = false| -> found:
                    if alphabet[j] == symbol:
                        found <- true
                        break
        return false if not present
    return true

# Log product of the selected sequence, preserving position order.
def sequence_log_weight(log_probs: view[f64], alphabet: view[i64], selected: view[i64]) -> f64 can[Abort.Panic]:
    width: i64 = alphabet.len.i64()
    indexed: bool = indexed_alphabet(alphabet)
    ordered: bool = selected.len.i64() >= 16 and width >= 16 and not indexed and ordered_alphabet(alphabet)
    lookup: darray[i64] = alphabet_columns(alphabet, width) if width >= 16 and not indexed and not ordered else []
    total, failed =
        for k in 0..<selected.len.i64() |total: f64 = 0.0, failed: bool = false| -> (total, failed):
            symbol: i64 = selected[k]
            column: i64 =
                if indexed:
                    symbol if symbol >= 0 and symbol < width else -1
                elif lookup.count > 0 and symbol >= 0 and symbol < width:
                    lookup[symbol]
                elif ordered:
                    ordered_column(alphabet, symbol, true)
                else:
                    for c in 0..<width |found: i64 = -1| -> found:
                        if alphabet[c] == symbol:
                            found <- c
                            break
            return log(0.0) if column < 0
            reading: f64 = log_probs[k * width + column]
            return log(0.0) if reading == log(0.0)
            if not failed:
                value: f64 = total + reading
                if value > -67108864.0 and value < 67108864.0:
                    total <- value
                else:
                    checked: f64 = partition_log_product(total, reading)
                    if checked != checked:
                        failed <- true
                    else:
                        total <- checked
    return log(-1.0) if failed
    return total

# Validate a complete prefix term and sum its selected log weights.
# Empty output denotes invalid shape or syntax; [-inf] is zero mass and [nan] is arithmetic failure.
def accepted_log_weight(log_probs: view[f64], alphabet: view[i64], selected: view[i64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    width: i64 = alphabet.len.i64()
    m: i64 = selected.len.i64()
    return [] if not matrix_shape(log_probs.len.i64(), m, width)
    indexed: bool = width >= 16 and indexed_alphabet(alphabet)
    lookup: darray[i64] = alphabet_columns(alphabet, m) if width >= 16 and not indexed else []
    pending, total, zero, failed =
        for k in 0..<m |pending: i64 = 1, total: f64 = 0.0, zero: bool = false, failed: bool = false| -> (pending, total, zero, failed):
            arity: i64 = selected[k]
            # Bound pending by the remaining symbols before adding this arity.
            return [] if pending == 0 or arity < 0 or arity > m - k - pending
            column: i64 =
                if width < 16:
                    for c in 0..<width |found: i64 = -1| -> found:
                        if alphabet[c] == arity:
                            found <- c
                            break
                elif indexed:
                    arity if arity < width else -1
                else:
                    lookup[arity]
            return [] if column < 0
            pending <- pending - 1 + arity
            reading: f64 = log_probs[k * width + column]
            if reading == log(0.0):
                zero <- true
            else:
                if not zero and not failed:
                    value: f64 = total + reading
                    if value > -67108864.0 and value < 67108864.0:
                        total <- value
                    else:
                        checked: f64 = partition_log_product(total, reading)
                        if checked != checked:
                            failed <- true
                        else:
                            total <- checked
    return [] if pending != 0
    return [log(0.0)] if zero
    return [log(-1.0)] if failed
    return [total]
