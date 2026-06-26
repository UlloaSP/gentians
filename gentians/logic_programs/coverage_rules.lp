extended_p(I):- pos_exs(I), cpi(I), not cpe(I).
extended_n(I):- neg_exs(I), cni(I), not cne(I).

#show extended_p/1.
#show extended_n/1.
