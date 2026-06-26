from gentians.rule_generation.variable_placement import VariablePlacer


def benchmark_place_variables(sampled_stub: str, unbalanced: bool = True):
    vp = VariablePlacer(unbalanced_aggregates=unbalanced)
    res = vp._place_variables_clause(sampled_stub)
    return len(res) > 0


def test_benchmark_0(benchmark):
    stub = ":- a(__VAR__,__VAR__),a(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_1(benchmark):
    stub = " :- x(__VAR__,__VAR__,__VAR__), x(__VAR__,__VAR__,__VAR__), less_than(__VAR__,__VAR__, __VAR__,__VAR__), __VAR__ >= __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_2(benchmark):
    stub = ":- #sum{__VAR__:x(__VAR__),size(__VAR__)}=__VAR__,__VAR__!=__VAR__,size(__VAR__),sum_col(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_3(benchmark):
    stub = "sum_partition(__VAR__,__VAR__):- #sum{__VAR__:p(__VAR__,__VAR__)}=__VAR__,partition(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_4(benchmark):
    stub = ":- #sum{__VAR__:p(__VAR__,__VAR__)}=__VAR__, #sum{__VAR__:p(__VAR__,__VAR__)}=__VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_5(benchmark):
    stub = ":- #sum{__VAR__:p(__VAR__,__VAR__)}=__VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_6(benchmark):
    stub = ":- __VAR__+__VAR__=__VAR__,__VAR__-__VAR__=__VAR__,__VAR__<__VAR__,__VAR__==__VAR__,q(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_7(benchmark):
    stub = ":- __VAR__+__VAR__=__VAR__,__VAR__>__VAR__,q(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_8(benchmark):
    stub = ":- __VAR__+__VAR__=__VAR__,q(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_9(benchmark):
    stub = ":- q(__VAR__,__VAR__,__VAR__),q(__VAR__,__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_10(benchmark):
    stub = ":- #sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__,#sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__,__VAR__+__VAR__=__VAR__,s1(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_11(benchmark):
    stub = ":- __VAR__==__VAR__,q(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_12(benchmark):
    stub = ":- __VAR__-__VAR__=__VAR__,__VAR__<__VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_13(benchmark):
    stub = ":- __VAR__>__VAR__,q(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_14(benchmark):
    stub = ":- q(__VAR__,__VAR__),q(__VAR__,__VAR__),a(__VAR__),a(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_15(benchmark):
    stub = "sp(__VAR__,__VAR__):- #sum{__VAR__,__VAR__:p(__VAR__,__VAR__)}=__VAR__, partition(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_16(benchmark):
    stub = ":- __VAR__-__VAR__=__VAR__,__VAR__<=__VAR__,hd(__VAR__),pos(__VAR__),sd(__VAR__),v1(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_17(benchmark):
    stub = ":- #sum{__VAR__,__VAR__:d(__VAR__,__VAR__)}=__VAR__,__VAR__-__VAR__=__VAR__,__VAR__>=__VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_18(benchmark):
    stub = "s0(__VAR__):- #sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__,#sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_19(benchmark):
    stub = "s1(__VAR__):- #sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__,#sum{__VAR__,__VAR__:el(__VAR__,__VAR__)}=__VAR__,s1(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_20(benchmark):
    stub = "odd(__VAR__):- even(__VAR__), prev(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_21(benchmark):
    stub = "a(__VAR__):- __VAR__ + __VAR__ = __VAR__, b(__VAR__), c(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_22(benchmark):
    stub = ":- #sum{ __VAR__,__VAR__ : el  ( __VAR__,__VAR__ )} = __VAR__,#sum{ __VAR__,__VAR__ : el  ( __VAR__,__VAR__ )} = __VAR__,s0(__VAR__),s1(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_23(benchmark):
    stub = "s(__VAR__,__VAR__):- g(__VAR__), h(__VAR__,__VAR__), i(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_24(benchmark):
    stub = "ok(__VAR__):- #sum{ __VAR__,__VAR__ : el  ( __VAR__,__VAR__ )} = __VAR__,#sum{ __VAR__,__VAR__ : el  ( __VAR__,__VAR__ )} = __VAR__,__VAR__ + __VAR__ = __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_25(benchmark):
    stub = ":- s(__VAR__), s(__VAR__), s(__VAR__), __VAR__ + __VAR__ = __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_26(benchmark):
    stub = (
        "s(__VAR__):- #sum{ __VAR__ : el  ( __VAR__ )} = __VAR__, __VAR__ != __VAR__."
    )
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_27(benchmark):
    stub = (
        ":- #sum{ __VAR__ : el  ( __VAR__ )} = __VAR__,__VAR__ != __VAR__,s(__VAR__)."
    )
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_28(benchmark):
    stub = "g(__VAR__):- #sum{ __VAR__, __VAR__ : a  ( __VAR__, __VAR__ )} = __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_29(benchmark):
    stub = "g(__VAR__):- #sum{ __VAR__ : a  ( __VAR__ )} = __VAR__, #sum{ __VAR__ : a  ( __VAR__ )} = __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert not result


def test_benchmark_30(benchmark):
    stub = "g(__VAR__):- #sum{ __VAR__ : a  ( __VAR__ )} = __VAR__."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_31(benchmark):
    stub = "count_row(__VAR__,__VAR__):- __VAR__ = #count{__VAR__ : x(__VAR__,__VAR__,__VAR__), cell(__VAR__)}, cell(__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result


def test_benchmark_32(benchmark):
    stub = ":- in(__VAR__), in(__VAR__), v(__VAR__), v(__VAR__), __VAR__!=__VAR__, not e(__VAR__,__VAR__), not e(__VAR__,__VAR__)."
    result = benchmark(benchmark_place_variables, stub)
    assert result
