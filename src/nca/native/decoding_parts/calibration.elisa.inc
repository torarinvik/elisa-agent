def calibrated_difference(value: f64, anchor: f64, temperature: f64) -> f64:
    difference: f64 = value - anchor
    return value / temperature - anchor / temperature if temperature > 1.0 and difference == log(0.0) and value != log(0.0) else difference / temperature

# Scale finite-or-negative-infinite rows into caller-owned binary64 storage.
def scaled_logit_rows_into(values: view[f64], output: mutable view[f64], width: i64, temperature: f64) -> i64 can[Abort.Panic]:
    return -1 if width <= 0 or values.len.i64() == 0 or output.len.i64() != values.len.i64() or values.len.i64() % width != 0
    return -1 if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    for row in 0..<(values.len.i64() / width):
        base: i64 = row * width
        maximum: f64 =
            for j in 0..<width |maximum: f64 = log(0.0)| -> maximum:
                value: f64 = values[base + j]
                return -1 if value != value or value == -log(0.0)
                maximum <- value if value > maximum else maximum
        return -1 if maximum == log(0.0)
        for j in 0..<width:
            output[base + j] <- calibrated_difference(values[base + j], maximum, temperature)
    return 0

# Shift integer logits by their maximum before converting to binary64.
# Unsigned inputs are passed as their bitwise-identical signed representation.
def shifted_integer_rows_into(values: view[i64], output: mutable view[f64], width: i64, unsigned: bool) -> i64 can[Abort.Panic]:
    return -1 if width <= 0 or values.len.i64() == 0 or output.len.i64() != values.len.i64() or values.len.i64() % width != 0
    minimum: i64 = -9223372036854775807 - 1
    for row in 0..<(values.len.i64() / width):
        base: i64 = row * width
        maximum: i64 =
            for j in 1..<width |maximum: i64 = values[base]| -> maximum:
                value: i64 = values[base + j]
                larger: bool = (value < 0 and maximum >= 0) or ((value < 0) == (maximum < 0) and value > maximum) if unsigned else value > maximum
                maximum <- value if larger else maximum
        for j in 0..<width:
            value: i64 = values[base + j]
            if unsigned and maximum < 0 and value >= 0:
                distance: f64 = (maximum - minimum).f64() + (9223372036854775807 - value).f64() + 1.0
                output[base + j] <- 0.0 - distance
            elif not unsigned and maximum > 0 and value < minimum + maximum:
                output[base + j] <- value.f64() - maximum.f64()
            else:
                output[base + j] <- (value - maximum).f64()
    return 0

def shifted_integer_logits_into(values: view[i64], output: mutable view[f64], unsigned: bool) -> i64 can[Abort.Panic]:
    return shifted_integer_rows_into(values, output, values.len.i64(), unsigned)

# Find the group of a label in a small validated class list.
def calibration_small_group(label: i64, classes: view[i64], groups: view[i64]) -> i64 can[Abort.Panic]:
    return
        for i in 0..<classes.len.i64() |group: i64 = -1| -> group:
            group <- groups[i] if classes[i] == label else group

def calibration_subset_sparse(labels: view[i64], classes: view[i64], groups: view[i64], width: i64, entries: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    for i in 0..<classes.len.i64():
        return [-1] if classes[i] < 0 or classes[i] >= width or groups[i] < 0 or groups[i] >= entries
        for j in 0..<i:
            return [-1] if classes[i] == classes[j]
    count: i64 =
        for i in 0..<labels.len.i64() |count: i64 = 0| -> count:
            count += 1 if calibration_small_group(labels[i], classes, groups) >= 0 else 0
    return [-1] if count > 4611686018427387903
    result: darray[i64] = [0 for _ in 0..<(count * 2)]
    for i in 0..<labels.len.i64() |next: i64 = 0|:
        group: i64 = calibration_small_group(labels[i], classes, groups)
        if group >= 0:
            result[next] <- i
            result[count + next] <- group
            next += 1
    return result

# Match held-out labels to decision groups, returning row indices followed by
# their group labels. A single -1 reports invalid mapping metadata.
def calibration_subset(labels: view[i64], classes: view[i64], groups: view[i64], width: i64, entries: i64) -> darray[i64] can[Memory.Allocate, Abort.Panic]:
    return [-1] if width <= 0 or entries <= 0 or classes.len.i64() != groups.len.i64()
    return [] if classes.len.i64() == 0
    return calibration_subset_sparse(labels, classes, groups, width, entries) if width > 4096 and classes.len.i64() <= 16 and labels.len.i64() <= width / (2 * classes.len.i64())
    lookup: darray[i64] = [-1 for _ in 0..<width]
    for i in 0..<classes.len.i64():
        index: i64 = classes[i]
        return [-1] if index < 0 or index >= width or groups[i] < 0 or groups[i] >= entries
        return [-1] if lookup[index] >= 0
        lookup[index] <- groups[i]
    count: i64 =
        for i in 0..<labels.len.i64() |count: i64 = 0| -> count:
            label: i64 = labels[i]
            count += 1 if label >= 0 and label < width and lookup[label] >= 0 else 0
    return [-1] if count > 4611686018427387903
    result: darray[i64] = [0 for _ in 0..<(count * 2)]
    for i in 0..<labels.len.i64() |next: i64 = 0|:
        label: i64 = labels[i]
        if label >= 0 and label < width and lookup[label] >= 0:
            result[next] <- i
            result[count + next] <- lookup[label]
            next += 1
    return result

# Mean grouped negative log-likelihood for each supplied temperature.
# An empty result asks the caller to use its reference implementation.
def calibration_singleton_loss_grid(logits: view[f64], labels: view[i64], temperatures: view[f64], rows: i64, width: i64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    maxima: darray[f64] = [log(0.0) for _ in 0..<rows]
    for row in 0..<rows:
        return [] if labels[row] < 0 or labels[row] >= width
        for j in 0..<width:
            value: f64 = logits[row * width + j]
            return [] if value != value or value == log(0.0) or value == -log(0.0)
            maxima[row] <- value if value > maxima[row] else maxima[row]
    result: darray[f64] = [0.0 for _ in 0..<temperatures.len.i64()]
    for t in 0..<temperatures.len.i64():
        temperature: f64 = temperatures[t]
        return [] if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
        loss: f64 =
            for row in 0..<rows |loss: f64 = 0.0| -> loss:
                maximum: f64 = maxima[row]
                target: f64 = logits[row * width + labels[row]]
                total: f64 =
                    for j in 0..<width |total: f64 = 0.0| -> total:
                        value: f64 = logits[row * width + j]
                        total += 1.0 if value == maximum else exp(calibrated_difference(value, maximum, temperature))
                loss += calibrated_difference(target, maximum, temperature) * -1.0 + log(total)
        result[t] <- loss / rows.f64()
    return result

def calibration_loss_grid(logits: view[f64], labels: view[i64], groups: view[i64], entries: i64, temperatures: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    rows: i64 = labels.len.i64()
    width: i64 = groups.len.i64()
    return [] if entries <= 0 or temperatures.len.i64() == 0 or not matrix_shape(logits.len.i64(), rows, width)
    for j in 0..<width:
        return [] if groups[j] < 0 or groups[j] >= entries
    singleton: bool =
        for j in 0..<width |identity: bool = entries == width| -> identity:
            identity <- false if groups[j] != j else identity
    return calibration_singleton_loss_grid(logits, labels, temperatures, rows, width) if singleton
    maxima: darray[f64] = [log(0.0) for _ in 0..<rows]
    target_maxima: darray[f64] = [log(0.0) for _ in 0..<rows]
    target_sizes: darray[i64] = [0 for _ in 0..<rows]
    for row in 0..<rows:
        return [] if labels[row] < 0 or labels[row] >= entries
        for j in 0..<width:
            value: f64 = logits[row * width + j]
            return [] if value != value or value == log(0.0) or value == -log(0.0)
            maxima[row] <- value if value > maxima[row] else maxima[row]
            target_maxima[row] <- value if groups[j] == labels[row] and value > target_maxima[row] else target_maxima[row]
            target_sizes[row] <- target_sizes[row] + 1 if groups[j] == labels[row] else target_sizes[row]
        return [] if target_maxima[row] == log(0.0)
    result: darray[f64] = [0.0 for _ in 0..<temperatures.len.i64()]
    for t in 0..<temperatures.len.i64():
        temperature: f64 = temperatures[t]
        return [] if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
        loss: f64 =
            for row in 0..<rows |loss: f64 = 0.0| -> loss:
                maximum: f64 = maxima[row]
                target_max: f64 = target_maxima[row]
                if target_sizes[row] == 1:
                    total: f64 =
                        for j in 0..<width |total: f64 = 0.0| -> total:
                            value: f64 = logits[row * width + j]
                            total += 1.0 if value == maximum else exp(calibrated_difference(value, maximum, temperature))
                    loss += calibrated_difference(target_max, maximum, temperature) * -1.0 + log(total)
                else:
                    total, target_total =
                        for j in 0..<width |total: f64 = 0.0, target_total: f64 = 0.0| -> (total, target_total):
                            value: f64 = logits[row * width + j]
                            total += 1.0 if value == maximum else exp(calibrated_difference(value, maximum, temperature))
                            target_total += (1.0 if value == target_max else exp(calibrated_difference(value, target_max, temperature))) if groups[j] == labels[row] else 0.0
                    loss += calibrated_difference(target_max, maximum, temperature) * -1.0 + log(total) - log(target_total)
        result[t] <- loss / rows.f64()
    return result

# Preserve the ordinary grid calculation, rescaling only overflowing means.
def calibration_loss_grid_stable(logits: view[f64], labels: view[i64], groups: view[i64], entries: i64, temperatures: view[f64]) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    result: darray[f64] = calibration_loss_grid(logits, labels, groups, entries, temperatures)
    return result if result.count != temperatures.len.i64()
    rows: i64 = labels.len.i64()
    width: i64 = groups.len.i64()
    overflowed: bool =
        for t in 0..<temperatures.len.i64() |found: bool = false| -> found:
            found <- true if result[t] == -log(0.0) else found
    return result if not overflowed
    maxima: darray[f64] = [log(0.0) for _ in 0..<rows]
    target_maxima: darray[f64] = [log(0.0) for _ in 0..<rows]
    for row in 0..<rows:
        for j in 0..<width:
            value: f64 = logits[row * width + j]
            maxima[row] <- value if value > maxima[row] else maxima[row]
            target_maxima[row] <- value if groups[j] == labels[row] and value > target_maxima[row] else target_maxima[row]
    for t in 0..<temperatures.len.i64():
        continue if result[t] != -log(0.0)
        temperature: f64 = temperatures[t]
        mean: f64 =
            for row in 0..<rows |mean: f64 = 0.0| -> mean:
                maximum: f64 = maxima[row]
                target_max: f64 = target_maxima[row]
                total, target_total =
                    for j in 0..<width |total: f64 = 0.0, target_total: f64 = 0.0| -> (total, target_total):
                        value: f64 = logits[row * width + j]
                        total += 1.0 if value == maximum else exp(calibrated_difference(value, maximum, temperature))
                        target_total += (1.0 if value == target_max else exp(calibrated_difference(value, target_max, temperature))) if groups[j] == labels[row] else 0.0
                gap: f64 = -calibrated_difference(target_max, maximum, temperature * rows.f64())
                mean += gap + (log(total) - log(target_total)) / rows.f64()
        result[t] <- mean
    return result

# Risk of a selected entry under nonnegative, not necessarily normalized weights.
# A negative result signals invalid weights, group ids or a selected index.
def weighted_decision_risk(weights: view[f64], groups: view[i64], entries: i64, selected: i64) -> f64 can[Abort.Panic]:
    return -1.0 if weights.len.i64() == 0 or weights.len.i64() != groups.len.i64() or entries <= 0 or selected < -1 or selected >= weights.len.i64()
    largest, top =
        for i in 0..<weights.len.i64() |largest: f64 = 0.0, top: i64 = 0| -> (largest, top):
            value: f64 = weights[i]
            return -1.0 if value != value or value < 0.0 or value == -log(0.0) or groups[i] < 0 or groups[i] >= entries
            top <- i if value > largest else top
            largest <- value if value > largest else largest
    return -1.0 if largest == 0.0
    chosen: i64 = groups[top if selected == -1 else selected]
    total, outside =
        for i in 0..<weights.len.i64() |total: f64 = 0.0, outside: f64 = 0.0| -> (total, outside):
            total += weights[i]
            outside += weights[i] if groups[i] != chosen else 0.0
    if total != -log(0.0):
        value: f64 = outside / total
        return nextafter(0.0, 1.0) if value == 0.0 and outside > 0.0 else value
    scaled_total, scaled_outside =
        for i in 0..<weights.len.i64() |total: f64 = 0.0, outside: f64 = 0.0| -> (total, outside):
            scaled: f64 = weights[i] / largest
            total += scaled
            outside += scaled if groups[i] != chosen else 0.0
    value: f64 = (outside / largest) / scaled_total if outside != -log(0.0) else scaled_outside / scaled_total
    return nextafter(0.0, 1.0) if value == 0.0 and outside > 0.0 else value

# Batched grouped probabilities or log probabilities in caller-owned storage.
def calibrated_group_rows_into(logits: view[f64], groups: view[i64], output: mutable view[f64], entries: i64, temperature: f64, logarithmic: bool) -> i64 can[Memory.Allocate, Abort.Panic]:
    width: i64 = groups.len.i64()
    return -1 if width <= 0 or entries <= 0 or logits.len.i64() % width != 0 or output.len.i64() % entries != 0
    return -1 if logits.len.i64() / width != output.len.i64() / entries
    return -1 if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    for j in 0..<width:
        return -1 if groups[j] < 0 or groups[j] >= entries
    maxima: darray[f64] = [log(0.0) for _ in 0..<entries]
    totals: darray[f64] = [0.0 for _ in 0..<entries]
    state: darray[f64] = [log(0.0)]
    for row in 0..<(logits.len.i64() / width):
        base: i64 = row * width
        out: i64 = row * entries
        for g in 0..<entries:
            maxima[g] <- log(0.0)
            totals[g] <- 0.0
            output[out + g] <- 0.0
        state[0] <- log(0.0)
        for j in 0..<width:
            value: f64 = logits[base + j]
            return -1 if value != value or value == -log(0.0)
            group: i64 = groups[j]
            maxima[group] <- value if value > maxima[group] else maxima[group]
            state[0] <- value if value > state[0] else state[0]
        largest: f64 = state[0]
        return -1 if largest == log(0.0)
        total: f64 =
            for j in 0..<width |total: f64 = 0.0| -> total:
                total += exp(calibrated_difference(logits[base + j], largest, temperature))
        for j in 0..<width:
            group: i64 = groups[j]
            value: f64 = logits[base + j]
            if logarithmic:
                totals[group] <- totals[group] + exp(calibrated_difference(value, maxima[group], temperature)) if maxima[group] != log(0.0) else totals[group]
            else:
                output[out + group] <- output[out + group] + exp(calibrated_difference(value, largest, temperature)) / total
        if logarithmic:
            normalizer: f64 = log(total)
            for g in 0..<entries:
                output[out + g] <- calibrated_difference(maxima[g], largest, temperature) + log(totals[g]) - normalizer if maxima[g] != log(0.0) else log(0.0)
    return 0

# Stable temperature-scaled softmax, summed into caller-declared groups.
def calibrated_groups(logits: view[f64], groups: view[i64], entries: i64, temperature: f64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return [] if logits.len.i64() == 0 or groups.len.i64() != logits.len.i64() or entries <= 0 or temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    largest: f64 =
        for k in 0..<logits.len.i64() |largest: f64 = log(0.0)| -> largest:
            return [] if logits[k] != logits[k] or logits[k] == -log(0.0) or groups[k] < 0 or groups[k] >= entries
            largest <- logits[k] if logits[k] > largest else largest
    return [] if largest == log(0.0)
    weights: darray[f64] = [exp(calibrated_difference(logits[k], largest, temperature)) for k in 0..<logits.len.i64()]
    total: f64 =
        for k in 0..<weights.count |total: f64 = 0.0| -> total:
            total += weights[k]
    return
        for k in 0..<weights.count |result: darray[f64] = [0.0 for _ in 0..<entries]| -> result:
            result[groups[k]] <- result[groups[k]] + weights[k] / total

# Group probabilities in log space, preserving finite underflowed masses.
def calibrated_log_groups(logits: view[f64], groups: view[i64], entries: i64, temperature: f64) -> darray[f64] can[Memory.Allocate, Abort.Panic]:
    return [] if logits.len.i64() == 0 or groups.len.i64() != logits.len.i64() or entries <= 0 or temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    maxima: darray[f64] = [log(0.0) for _ in 0..<entries]
    state: darray[f64] = [log(0.0), 0.0]
    for k in 0..<logits.len.i64():
        group: i64 = groups[k]
        return [] if group < 0 or group >= entries or logits[k] != logits[k] or logits[k] == -log(0.0)
        maxima[group] <- logits[k] if logits[k] > maxima[group] else maxima[group]
        state[0] <- logits[k] if logits[k] > state[0] else state[0]
    largest: f64 = state[0]
    return [] if largest == log(0.0)
    totals: darray[f64] = [0.0 for _ in 0..<entries]
    for k in 0..<logits.len.i64():
        group: i64 = groups[k]
        totals[group] <- totals[group] + exp(calibrated_difference(logits[k], maxima[group], temperature)) if maxima[group] != log(0.0) else totals[group]
        state[1] <- state[1] + exp(calibrated_difference(logits[k], largest, temperature))
    return [calibrated_difference(maxima[g], largest, temperature) + log(totals[g]) - log(state[1]) if maxima[g] != log(0.0) else log(0.0) for g in 0..<entries]

def risk_at_offset(logits: view[f64], groups: view[i64], base: i64, width: i64, chosen: i64, temperature: f64, largest: f64) -> f64 can[Memory.Allocate, Abort.Panic]:
    total, outside =
        for i in 0..<width |total: f64 = 0.0, outside: f64 = 0.0| -> (total, outside):
            weight: f64 = exp(calibrated_difference(logits[base + i], largest, temperature))
            total += weight
            group: i64 = i if groups.len.i64() == 0 else groups[i]
            outside += weight if group != chosen else 0.0
    result: f64 = outside / total
    return result if result != 0.0
    largest_outside: f64 =
        for i in 0..<width |largest: f64 = log(0.0)| -> largest:
            group: i64 = i if groups.len.i64() == 0 else groups[i]
            largest <- logits[base + i] if group != chosen and logits[base + i] > largest else largest
    return 0.0 if largest_outside == log(0.0)
    scaled: f64 =
        for i in 0..<width |sum: f64 = 0.0| -> sum:
            group: i64 = i if groups.len.i64() == 0 else groups[i]
            sum += exp(calibrated_difference(logits[base + i], largest_outside, temperature)) if group != chosen else 0.0
    recovered: f64 = exp(calibrated_difference(largest_outside, largest, temperature) + log(scaled) - log(total))
    return nextafter(0.0, 1.0) if recovered == 0.0 else recovered

def risk_at_anchor(logits: view[f64], groups: view[i64], chosen: i64, temperature: f64, largest: f64) -> f64 can[Memory.Allocate, Abort.Panic]:
    return risk_at_offset(logits, groups, 0, logits.len.i64(), chosen, temperature, largest)

# Calibrated decision risk per row, selected from the caller's reading.
def calibrated_risk_rows_into(logits: view[f64], reading: view[f64], groups: view[i64], output: mutable view[f64], width: i64, entries: i64, temperature: f64) -> i64 can[Memory.Allocate, Abort.Panic]:
    return -1 if width <= 0 or entries <= 0 or logits.len.i64() % width != 0
    return -1 if groups.len.i64() != width and groups.len.i64() != 0
    return -1 if groups.len.i64() == 0 and entries != width
    return -1 if reading.len.i64() != logits.len.i64() or output.len.i64() != logits.len.i64() / width
    return -1 if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    for j in 0..<groups.len.i64():
        return -1 if groups[j] < 0 or groups[j] >= entries
    for row in 0..<output.len.i64():
        base: i64 = row * width
        largest, top =
            for j in 0..<width |largest: f64 = log(0.0), top: i64 = 0| -> (largest, top):
                value: f64 = logits[base + j]
                order: f64 = reading[base + j]
                return -1 if value != value or value == -log(0.0) or order != order or order < 0.0 or order == -log(0.0)
                largest <- value if value > largest else largest
                top <- j if order > reading[base + top] else top
        return -1 if largest == log(0.0)
        chosen: i64 = top if groups.len.i64() == 0 else groups[top]
        output[row] <- risk_at_offset(logits, groups, base, width, chosen, temperature, largest)
    return 0

# Select each row using exact signed or unsigned integer weights.
def calibrated_integer_risk_rows_into(logits: view[f64], reading: view[i64], groups: view[i64], output: mutable view[f64], width: i64, entries: i64, temperature: f64, unsigned: bool) -> i64 can[Memory.Allocate, Abort.Panic]:
    return -1 if width <= 0 or entries <= 0 or logits.len.i64() % width != 0
    return -1 if groups.len.i64() != width and groups.len.i64() != 0
    return -1 if groups.len.i64() == 0 and entries != width
    return -1 if reading.len.i64() != logits.len.i64() or output.len.i64() != logits.len.i64() / width
    return -1 if temperature <= 0.0 or temperature != temperature or temperature == -log(0.0)
    for j in 0..<groups.len.i64():
        return -1 if groups[j] < 0 or groups[j] >= entries
    for row in 0..<output.len.i64():
        base: i64 = row * width
        largest, top =
            for j in 0..<width |largest: f64 = log(0.0), top: i64 = 0| -> (largest, top):
                value: f64 = logits[base + j]
                order: i64 = reading[base + j]
                return -1 if value != value or value == -log(0.0) or (not unsigned and order < 0)
                largest <- value if value > largest else largest
                current: i64 = reading[base + top]
                larger: bool = (order < 0 and current >= 0) or ((order < 0) == (current < 0) and order > current) if unsigned else order > current
                top <- j if larger else top
        return -1 if largest == log(0.0)
        chosen: i64 = top if groups.len.i64() == 0 else groups[top]
        output[row] <- risk_at_offset(logits, groups, base, width, chosen, temperature, largest)
    return 0

# Risk for a caller-selected class in a caller-declared partition.
def calibrated_risk_at(logits: view[f64], groups: view[i64], entries: i64, temperature: f64, top: i64) -> f64 can[Memory.Allocate, Abort.Panic]:
    return log(-1.0) if top < 0 or top >= logits.len.i64() or groups.len.i64() != logits.len.i64()
    largest: f64 =
        for k in 0..<logits.len.i64() |largest: f64 = log(0.0)| -> largest:
            largest <- logits[k] if logits[k] > largest else largest
    return risk_at_anchor(logits, groups, groups[top], temperature, largest)

# Choose from the caller's actual reading and charge its selected group.
def calibrated_risk_for_reading_checked(logits: view[f64], reading: view[f64], groups: view[i64], entries: i64, temperature: f64) -> f64 can[Memory.Allocate, Abort.Panic]:
    return log(-1.0) if logits.len.i64() == 0 or reading.len.i64() != logits.len.i64() or groups.len.i64() != logits.len.i64()
    return log(-1.0) if reading[0] != reading[0] or reading[0] < 0.0 or reading[0] == -log(0.0)
    top: i64 =
        for k in 1..<reading.len.i64() |top: i64 = 0| -> top:
            return log(-1.0) if reading[k] != reading[k] or reading[k] < 0.0 or reading[k] == -log(0.0)
            top <- k if reading[k] > reading[top] else top
    largest: f64 =
        for k in 0..<logits.len.i64() |largest: f64 = log(0.0)| -> largest:
            largest <- logits[k] if logits[k] > largest else largest
    return risk_at_anchor(logits, groups, groups[top], temperature, largest)

# Retain the existing export for clients built against earlier kernels.
def calibrated_risk_for_reading(logits: view[f64], reading: view[f64], groups: view[i64], entries: i64, temperature: f64) -> f64 can[Memory.Allocate, Abort.Panic]:
    return calibrated_risk_for_reading_checked(logits, reading, groups, entries, temperature)

# The legacy path selects the first largest individual logit.
def calibrated_risk(logits: view[f64], groups: view[i64], entries: i64, temperature: f64) -> f64 can[Memory.Allocate, Abort.Panic]:
    return log(-1.0) if logits.len.i64() == 0 or groups.len.i64() != logits.len.i64()
    top: i64 =
        for k in 0..<logits.len.i64() |top: i64 = 0| -> top:
            top <- k if logits[k] > logits[top] else top
    return risk_at_anchor(logits, groups, groups[top], temperature, logits[top])
