from gentians.variable_placer import VariablePlacer
from types import SimpleNamespace

# sampled_stub = ":- a(_____,_____),a(_____,_____)."
# sampled_stub = "d(V0,V0):- #sum{V1,V2:d(V2,V1)}=V0."
# sampled_stub = " :- x(_____,_____,_____), x(_____,_____,_____), less_than(_____,_____, _____,_____), _____ >= _____."
# sampled_stub = ":- #sum{_____:x(_____),size(_____)}=_____,_____!=_____,size(_____),sum_col(_____,_____)."
# sampled_stub = "sum_partition(_____,_____):- #sum{_____:p(_____,_____)}=_____,partition(_____)."
# sampled_stub = ":- #sum{_____:p(_____,_____)}=_____, #sum{_____:p(_____,_____)}=_____."
# sampled_stub = ":- #sum{_____:p(_____,_____)}=_____."
# sampled_stub = ":- _____+_____=_____,_____-_____=_____,_____<_____,_____==_____,q(_____,_____)."
# sampled_stub = ":- _____+_____=_____,_____>_____,q(_____,_____)." # qui attenzione che se ho > o < invece di == allora è unsafe
# sampled_stub = ":- _____+_____=_____,q(_____,_____)."
# sampled_stub = ":- q(_____,_____,_____),q(_____,_____,_____)."
# sampled_stub = ":- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,_____+_____=_____,s1(_____)."
# sampled_stub = ":- _____==_____,q(_____,_____)."
# sampled_stub = ":- _____-_____=_____,_____<_____."
# sampled_stub = ":- _____>_____,q(_____,_____)."
# sampled_stub = ":- q(_____,_____),q(_____,_____),a(_____),a(_____)."
# sampled_stub = "sp(_____,_____):- #sum{_____,_____:p(_____,_____)}=_____, partition(_____)."
# sampled_stub = ":- _____-_____=_____,_____<=_____,hd(_____),pos(_____),sd(_____),v1(_____,_____)."
# sampled_stub = ":- #sum{_____,_____:d(_____,_____)}=_____,_____-_____=_____,_____>=_____."
# sampled_stub = "s0(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____."
# sampled_stub = "s1(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,s1(_____)."
# sampled_stub = "odd(_____):- even(_____), prev(_____,_____)."

# sampled_stub = "a(_____):- _____ + _____ = _____, b(_____), c(_____)."
# sampled_stub = ":- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,s0(_____),s1(_____)."

# sampled_stub = "s(_____,_____):- g(_____), h(_____,_____), i(_____)."
# sampled_stub = "ok(_____):- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,_____ + _____ = _____."
# sampled_stub = ":- s(_____), s(_____), s(_____), _____ + _____ = _____."
# sampled_stub = "s(_____):- #sum{ _____ : el  ( _____ )} = _____, _____ != _____."
# sampled_stub = ":- #sum{ _____ : el  ( _____ )} = _____,_____ != _____,s(_____)."
# sampled_stub = "g(_____):- #sum{ _____, _____ : a  ( _____, _____ )} = _____."
# sampled_stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____, #sum{ _____ : a  ( _____ )} = _____."
# sampled_stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____."
# sampled_stub = "count_row(_____,_____):- _____ = #count{_____ : x(_____,_____,_____), cell(_____)}, cell(_____)."
# sampled_stub = ":- in(_____), in(_____), v(_____), v(_____), _____!=_____, not e(_____,_____), not e(_____,_____)."


def benchmark_place_variables(sampled_stub : str, unbalanced : bool = True):
    args = SimpleNamespace(
        verbosity=0,
        max_variables=3,
        unbalanced_agg=unbalanced,
        unbalanced_aggregates=unbalanced,
    )
    vp = VariablePlacer(args)
    res = vp.place_variables_list_of_clauses([sampled_stub])
    return len(res) > 0

def test_benchmark_0(benchmark):
    stub = ":- a(_____,_____),a(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_1(benchmark):
    stub = " :- x(_____,_____,_____), x(_____,_____,_____), less_than(_____,_____, _____,_____), _____ >= _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_2(benchmark):
    stub = ":- #sum{_____:x(_____),size(_____)}=_____,_____!=_____,size(_____),sum_col(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_3(benchmark):
    stub = "sum_partition(_____,_____):- #sum{_____:p(_____,_____)}=_____,partition(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_4(benchmark):
    stub = ":- #sum{_____:p(_____,_____)}=_____, #sum{_____:p(_____,_____)}=_____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_5(benchmark):
    stub = ":- #sum{_____:p(_____,_____)}=_____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_6(benchmark):
    stub = ":- _____+_____=_____,_____-_____=_____,_____<_____,_____==_____,q(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_7(benchmark):
    stub = ":- _____+_____=_____,_____>_____,q(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_8(benchmark):
    stub = ":- _____+_____=_____,q(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_9(benchmark):
    stub = ":- q(_____,_____,_____),q(_____,_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_10(benchmark):
    stub = ":- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,_____+_____=_____,s1(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_11(benchmark):
    stub = ":- _____==_____,q(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_12(benchmark):
    stub = ":- _____-_____=_____,_____<_____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_13(benchmark):
    stub = ":- _____>_____,q(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_14(benchmark):
    stub = ":- q(_____,_____),q(_____,_____),a(_____),a(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_15(benchmark):
    stub = "sp(_____,_____):- #sum{_____,_____:p(_____,_____)}=_____, partition(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_16(benchmark):
    stub = ":- _____-_____=_____,_____<=_____,hd(_____),pos(_____),sd(_____),v1(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_17(benchmark):
    stub = ":- #sum{_____,_____:d(_____,_____)}=_____,_____-_____=_____,_____>=_____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_18(benchmark):
    stub = "s0(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_19(benchmark):
    stub = "s1(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,s1(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_20(benchmark):
    stub = "odd(_____):- even(_____), prev(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_21(benchmark):
    stub = "a(_____):- _____ + _____ = _____, b(_____), c(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_22(benchmark):
    stub = ":- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,s0(_____),s1(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_23(benchmark):
    stub = "s(_____,_____):- g(_____), h(_____,_____), i(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_24(benchmark):
    stub = "ok(_____):- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,_____ + _____ = _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_25(benchmark):
    stub = ":- s(_____), s(_____), s(_____), _____ + _____ = _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_26(benchmark):
    stub = "s(_____):- #sum{ _____ : el  ( _____ )} = _____, _____ != _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_27(benchmark):
    stub = ":- #sum{ _____ : el  ( _____ )} = _____,_____ != _____,s(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_28(benchmark):
    stub = "g(_____):- #sum{ _____, _____ : a  ( _____, _____ )} = _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_29(benchmark):
    stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____, #sum{ _____ : a  ( _____ )} = _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_30(benchmark):
    stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_31(benchmark):
    stub = "count_row(_____,_____):- _____ = #count{_____ : x(_____,_____,_____), cell(_____)}, cell(_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 

def test_benchmark_32(benchmark):
    stub = ":- in(_____), in(_____), v(_____), v(_____), _____!=_____, not e(_____,_____), not e(_____,_____)."
    result = benchmark(benchmark_place_variables, stub)
    assert isinstance(result, bool) 
