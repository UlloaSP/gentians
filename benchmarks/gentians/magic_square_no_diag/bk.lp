#const n = 3.
size(1..n).
val(1..n*n).
1 { x(Row, Col, N) : val(N) } 1 :- size(Row), size(Col).
1 { x(Row, Col, N) : size(Row), size(Col) } 1 :- val(N).
