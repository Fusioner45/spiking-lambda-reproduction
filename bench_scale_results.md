# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 89 | 27 | 3.2 |
| 25 | 74 | 74 | 24 | 673 | 174 | 3.9 |
| 50 | 149 | 149 | 49 | 1947 | 488 | 4.0 |
| 100 | 299 | 299 | 99 | 8204 | 1063 | 7.7 |
| 150 | 449 | 449 | 149 | 16106 | 3079 | 5.2 |
| m55 | 36 | 83 | 13 | 1725 | 135 | 12.8 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
