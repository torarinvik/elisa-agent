# Compare flat matrix dimensions without multiplying signed lengths.
def matrix_shape(size: i64, rows: i64, columns: i64) -> bool:
    return false if size < 0 or rows <= 0 or columns <= 0
    return size / columns == rows and size % columns == 0

def valid_observation_weights(values: view[f64]) -> bool can[Abort.Panic]:
    return
        for i in 0..<values.len.i64() |positive: bool = false| -> positive:
            x: f64 = values[i]
            return false if x != x or x < 0.0 or x == -log(0.0)
            positive <- true if x > 0.0 else positive

# Validate nonnegative finite weights and produce their floored logarithms.
# An empty result signals an invalid vector (including an all-zero vector).
def observation_logs(values: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return [] if not valid_observation_weights(values)
    return [log(values[i] if values[i] > 0.0 else nextafter(0.0, 1.0)) for i in 0..<values.len.i64()]

def observation_logs_into(values: view[f64], output: mutable view[f64]) -> i64 can[Abort.Panic]:
    return -1 if output.len.i64() != values.len.i64() or not valid_observation_weights(values)
    for i in 0..<values.len.i64():
        output[i] <- log(values[i] if values[i] > 0.0 else nextafter(0.0, 1.0))
    return 0

# Sum finite nonnegative binary64 values, rounding each inexact addition up.
def upper_add(total: f64, x: f64) -> f64:
    rounded: f64 = total + x
    part: f64 = rounded - total
    residual: f64 = (total - (rounded - part)) + (x - part)
    return nextafter(rounded, -log(0.0)) if residual > 0.0 else rounded

def upper_sum(values: view[f64]) -> f64 can[Abort.Panic]:
    return
        for i in 0..<values.len.i64() |total: f64 = 0.0| -> total:
            total <- upper_add(total, values[i])

# Sum finite nonnegative binary64 values with downward rounding.
def lower_add(total: f64, x: f64) -> f64:
    rounded: f64 = total + x
    part: f64 = rounded - total
    residual: f64 = (total - (rounded - part)) + (x - part)
    return nextafter(rounded, 0.0) if residual < 0.0 or rounded == -log(0.0) else rounded

def lower_sum(values: view[f64]) -> f64 can[Abort.Panic]:
    return
        for i in 0..<values.len.i64() |total: f64 = 0.0| -> total:
            total <- lower_add(total, values[i])

def lower_product(a: f64, b: f64) -> f64:
    product: f64 = a * b
    return nextafter(product, 0.0) if product > 0.0 else 0.0

def lower_half(x: f64) -> f64:
    half: f64 = x * 0.5
    return nextafter(half, 0.0) if half + half > x else half

# Lower bounds for half the sum and the sum of unordered pair products.
def detection_floors(risks: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    state: darray[f64] = [0.0, 0.0]
    for i in 0..<risks.len.i64():
        state[1] <- lower_add(state[1], lower_product(state[0], risks[i]))
        state[0] <- lower_add(state[0], risks[i])
    return [lower_half(state[0]), state[1]]

# Upper-bounding products of nonnegative binary64 operands.
def upper_product(a: f64, b: f64) -> f64:
    product: f64 = a * b
    return product if a == 0.0 or b == 0.0 or product == -log(0.0)
    return nextafter(product, -log(0.0))

def upper_half(x: f64) -> f64:
    half: f64 = x * 0.5
    return nextafter(half, -log(0.0)) if half + half < x else half

def markov_shares(risks: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return [upper_half(risks[i]) for i in 0..<risks.len.i64()]

def combine_shares(shares: view[f64], within: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return [upper_add(shares[i], within[i]) for i in 0..<shares.len.i64()]

# Half of each item's risk times the sum of all other risks, without subtraction.
def pair_shares(risks: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    n: i64 = risks.len.i64()
    prefix: darray[f64] = [0.0 for _ in 0..<(n + 1)]
    suffix: darray[f64] = [0.0 for _ in 0..<(n + 1)]
    for i in 0..<n:
        prefix[i + 1] <- upper_add(prefix[i], risks[i])
        suffix[n - i - 1] <- upper_add(suffix[n - i], risks[n - i - 1])
    return [upper_product(upper_product(risks[i], upper_add(prefix[i], suffix[i + 1])), 0.5) for i in 0..<n]

# Return indices of rows with any unequal values, preserving row order.
def changed_rows(left: view[f64], right: view[f64], output: mutable view[i64], width: i64) -> i64 can[Abort.Panic]:
    return -1 if width <= 0 or left.len.i64() != right.len.i64()
    return -1 if left.len.i64() % width != 0
    rows: i64 = left.len.i64() / width
    return -1 if output.len.i64() < rows
    return
        for k in 0..<rows |count: i64 = 0, output| -> count:
            different: bool =
                for j in 0..<width |different: bool = false| -> different:
                    if left[k * width + j] != right[k * width + j]:
                        different <- true
                        break
            if different:
                output[count] <- k
                count += 1

# Map arities outside the usable range to its two sentinel boundaries.
def clamp_format_symbols(symbols: mutable view[i64], length: i64) -> i64 can[Abort.Panic]:
    for i in 0..<symbols.len.i64():
        if symbols[i] < -1:
            symbols[i] <- -1
        elif symbols[i] > length:
            symbols[i] <- length
    return 0

# Reinterpreted unsigned values with the high bit set are above any i64 length.
def clamp_unsigned_format_symbols(symbols: mutable view[i64], length: i64) -> i64 can[Abort.Panic]:
    for i in 0..<symbols.len.i64():
        if symbols[i] < 0 or symbols[i] > length:
            symbols[i] <- length
    return 0

# Validate the signed integer representation of a nonnegative arity sequence.
def nonnegative_arities(symbols: view[i64]) -> bool can[Abort.Panic]:
    for i in 0..<symbols.len.i64():
        return false if symbols[i] < 0
    return true

# Log weights may contain negative infinity but not NaN or positive infinity.
def valid_log_weights(rows: view[f64]) -> bool can[Abort.Panic]:
    for i in 0..<rows.len.i64():
        x: f64 = rows[i]
        return false if x != x or x == -log(0.0)
    return true

# Accept only rows comfortably inside the normalization tolerance. A false
# result asks the caller to run its full validator, including boundary cases.
def normalized_rows_fast(rows: view[f64], base: view[f64]) -> bool can[Abort.Panic]:
    width: i64 = base.len.i64()
    return false if width < 1 or width > 3 or rows.len.i64() % width != 0
    for k in 0..<(rows.len.i64() / width):
        total: f64 =
            for j in 0..<width |total: f64 = 0.0| -> total:
                x: f64 = rows[k * width + j]
                return false if x != x or x > 0.0 or (base[j] == log(0.0) and x != log(0.0))
                total += exp(x)
        return false if total < 1.0 - 9.0e-13 or total > 1.0 + 9.0e-13
    return true

# The log-weight of an unreachable state, and log Z when no sequence is accepted.
const FLOOR: f64 = -1.0e308

def live(k: i64, m: i64, max_arity: i64) -> i64:
    remaining: i64 = m - k
    return 0 if remaining == 0
    return 1 if k == 0 or max_arity <= 1
    growth: i64 = max_arity - 1
    return remaining if growth > (remaining - 1) / k
    return 1 + k * growth

# Detect invalid posterior rows without claiming a floating-point error bound.
def posterior_rows_valid(rows: view[f64], width: i64, tolerance: f64) -> bool can[Abort.Panic]:
    return false if width < 1 or rows.len.i64() % width != 0
    for k in 0..<(rows.len.i64() / width):
        total: f64 =
            for j in 0..<width |total: f64 = 0.0| -> total:
                value: f64 = rows[k * width + j]
                return false if value != value or value < 0.0 or value > 1.0 + tolerance
                total += value
        return false if total < 1.0 - tolerance or total > 1.0 + tolerance
    return true

# `log_probs` holds m rows of one log-probability per entry of `alphabet` (the arities).
# The result is [log Z, decoded arities (m), posterior marginals (m rows)], or [FLOOR] when
# no parseable sequence has positive weight.
