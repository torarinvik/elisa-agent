# 15. Normalization against shift

**Theory.** A normalizer `N : X → Y` is a module
placed before a recognizer, which is then trained and evaluated on normalized
inputs. A style shift is a map `T` applied to reference inputs, so the shifted
distribution is `T_*ν₀` and the recognizer sees `N_*T_*ν₀` instead of `N_*ν₀`.

| Theorem | Statement |
|---|---|
| 15.1 | normalization never increases a shift (data processing) |
| 15.2 | if `N ∘ T = N` on `G`, the normalized shift is at most `ν₀(Gᶜ)` |
| 15.3 | if `N ∘ T = N` everywhere, the shift is removed |

With §5 this gives the design rule: a normalizer pays off exactly to the
extent that it undoes the style, and no normalizer can help where the style
destroys the information that separates classes (then `N(T x) = N(T x')` for
`x`, `x'` of different classes, and any recognizer after `N` errs on one of
them).

[Theory index](../THEORY.md)
