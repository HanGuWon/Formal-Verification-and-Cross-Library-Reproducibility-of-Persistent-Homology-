# PH-CONFORMANCE-VR-001

## setup
- Generated at UTC: 2026-03-16T21:40:26.277305+00:00
- Python: `3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]`
- Platform: `Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Random seed: `0`
- Key distributions:
  - `numpy==2.4.3`
  - `scipy==1.17.1`
  - `gudhi==3.11.0`
  - `ripser==0.6.12`
  - `dionysus==2.1.8`
- Pairwise case agreement across all compared dimensions:
  - `gudhi__ripser` exact in `36/192` case(s)
  - `gudhi__dionysus` exact in `36/192` case(s)
  - `ripser__dionysus` exact in `192/192` case(s)

## benchmark definitions

| benchmark_id | family | mode | selected_threshold | full_threshold | has_point_cloud | distance_matrix_shape | distance_matrix_hash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tfim_obc_n4_g0p50__floating | A | floating | 1.2427812645009748 | 1.7594160005299657 | False | 4x4 | 38ff65464b09 |
| tfim_obc_n4_g0p50__quantized | A | quantized | 1.2431640625 | 1.759765625 | False | 4x4 | 50b73af87c25 |
| tfim_obc_n4_g1p00__floating | A | floating | 2.2583205186323103 | 9.73791661636864 | False | 4x4 | 8f1560788245 |
| tfim_obc_n4_g1p00__quantized | A | quantized | 2.2587890625 | 9.73828125 | False | 4x4 | b17ca8589e68 |
| tfim_obc_n6_g0p50__floating | A | floating | 1.2525237786025318 | 1.673685643721418 | False | 6x6 | 9f3351e65c9d |
| tfim_obc_n6_g0p50__quantized | A | quantized | 1.2529296875 | 1.673828125 | False | 6x6 | 9f3380f800fe |
| tfim_obc_n6_g1p00__floating | A | floating | 4.571710545762174 | 21.87969489144892 | False | 6x6 | 25887e794564 |
| tfim_obc_n6_g1p00__quantized | A | quantized | 4.5712890625 | 21.8798828125 | False | 6x6 | 49ff68439dd0 |
| tfim_pbc_n4_g0p50__floating | A | floating | 1.119133843184316 | 1.1405648750053994 | False | 4x4 | 3512251ede57 |
| tfim_pbc_n4_g0p50__quantized | A | quantized | 1.119140625 | 1.140625 | False | 4x4 | 499f4a50645b |
| tfim_pbc_n4_g1p00__floating | A | floating | 1.7308043394454913 | 2.0553334879376455 | False | 4x4 | 4ea00fb970ef |
| tfim_pbc_n4_g1p00__quantized | A | quantized | 1.73046875 | 2.0556640625 | False | 4x4 | 7d7b9bbefb71 |
| tfim_pbc_n6_g0p50__floating | A | floating | 1.1276651550305354 | 1.130663291251138 | False | 6x6 | a0d257bb4f73 |
| tfim_pbc_n6_g0p50__quantized | A | quantized | 1.1279296875 | 1.130859375 | False | 6x6 | cadaccc66f23 |
| tfim_pbc_n6_g1p00__floating | A | floating | 2.497817855094092 | 2.7097514512720444 | False | 6x6 | 02dc5c8900df |
| tfim_pbc_n6_g1p00__quantized | A | quantized | 2.498046875 | 2.7099609375 | False | 6x6 | 4916ff089142 |
| square_patch_3x3__floating | B | floating | 1.0 | 2.8284271247461903 | True | 9x9 | 0a4a6107ee5a |
| square_patch_3x3__quantized | B | quantized | 1.0 | 2.828125 | True | 9x9 | 6b119c77f3a9 |
| triangular_patch_3x3__floating | B | floating | 1.0 | 2.6457513110645907 | True | 9x9 | 68a205222b6c |
| triangular_patch_3x3__quantized | B | quantized | 1.0 | 2.6455078125 | True | 9x9 | 5879f7278c85 |
| honeycomb_patch_2x2__floating | B | floating | 1.0 | 4.0 | True | 8x8 | 2b43da87ebce |
| honeycomb_patch_2x2__quantized | B | quantized | 1.0 | 4.0 | True | 8x8 | 905c07d43ffe |
| nacl_coordination_shell__floating | B | floating | 1.0 | 2.0 | True | 7x7 | 5a31949863d6 |
| nacl_coordination_shell__quantized | B | quantized | 1.0 | 2.0 | True | 7x7 | 4664e10abe61 |

## per-benchmark agreement table

| benchmark_id | mode | coeff | maxdim | threshold | exact_all | mismatch_dims |
| --- | --- | --- | --- | --- | --- | --- |
| tfim_obc_n4_g0p50__floating | floating | 2 | 1 | selected | False | 0 |
| tfim_obc_n4_g0p50__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_obc_n4_g0p50__floating | floating | 2 | 2 | selected | False | 0 |
| tfim_obc_n4_g0p50__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_obc_n4_g0p50__floating | floating | 3 | 1 | selected | False | 0 |
| tfim_obc_n4_g0p50__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_obc_n4_g0p50__floating | floating | 3 | 2 | selected | False | 0 |
| tfim_obc_n4_g0p50__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_obc_n4_g0p50__quantized | quantized | 2 | 1 | selected | True | - |
| tfim_obc_n4_g0p50__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_obc_n4_g0p50__quantized | quantized | 2 | 2 | selected | True | - |
| tfim_obc_n4_g0p50__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_obc_n4_g0p50__quantized | quantized | 3 | 1 | selected | True | - |
| tfim_obc_n4_g0p50__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_obc_n4_g0p50__quantized | quantized | 3 | 2 | selected | True | - |
| tfim_obc_n4_g0p50__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_obc_n4_g1p00__floating | floating | 2 | 1 | selected | False | 0 |
| tfim_obc_n4_g1p00__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_obc_n4_g1p00__floating | floating | 2 | 2 | selected | False | 0 |
| tfim_obc_n4_g1p00__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_obc_n4_g1p00__floating | floating | 3 | 1 | selected | False | 0 |
| tfim_obc_n4_g1p00__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_obc_n4_g1p00__floating | floating | 3 | 2 | selected | False | 0 |
| tfim_obc_n4_g1p00__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_obc_n4_g1p00__quantized | quantized | 2 | 1 | selected | True | - |
| tfim_obc_n4_g1p00__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_obc_n4_g1p00__quantized | quantized | 2 | 2 | selected | True | - |
| tfim_obc_n4_g1p00__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_obc_n4_g1p00__quantized | quantized | 3 | 1 | selected | True | - |
| tfim_obc_n4_g1p00__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_obc_n4_g1p00__quantized | quantized | 3 | 2 | selected | True | - |
| tfim_obc_n4_g1p00__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_obc_n6_g0p50__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 2 | 2 | selected | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_obc_n6_g0p50__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 3 | 2 | selected | False | 0,1 |
| tfim_obc_n6_g0p50__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_obc_n6_g0p50__quantized | quantized | 2 | 1 | selected | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 2 | 2 | selected | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_obc_n6_g0p50__quantized | quantized | 3 | 1 | selected | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 3 | 2 | selected | False | 1 |
| tfim_obc_n6_g0p50__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_obc_n6_g1p00__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 2 | 2 | selected | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_obc_n6_g1p00__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 3 | 2 | selected | False | 0,1 |
| tfim_obc_n6_g1p00__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_obc_n6_g1p00__quantized | quantized | 2 | 1 | selected | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 2 | 2 | selected | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_obc_n6_g1p00__quantized | quantized | 3 | 1 | selected | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 3 | 2 | selected | False | 1 |
| tfim_obc_n6_g1p00__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_pbc_n4_g0p50__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 2 | 2 | selected | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_pbc_n4_g0p50__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 3 | 2 | selected | False | 0,1 |
| tfim_pbc_n4_g0p50__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_pbc_n4_g0p50__quantized | quantized | 2 | 1 | selected | True | - |
| tfim_pbc_n4_g0p50__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_pbc_n4_g0p50__quantized | quantized | 2 | 2 | selected | True | - |
| tfim_pbc_n4_g0p50__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_pbc_n4_g0p50__quantized | quantized | 3 | 1 | selected | True | - |
| tfim_pbc_n4_g0p50__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_pbc_n4_g0p50__quantized | quantized | 3 | 2 | selected | True | - |
| tfim_pbc_n4_g0p50__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_pbc_n4_g1p00__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 2 | 2 | selected | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_pbc_n4_g1p00__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 3 | 2 | selected | False | 0,1 |
| tfim_pbc_n4_g1p00__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_pbc_n4_g1p00__quantized | quantized | 2 | 1 | selected | True | - |
| tfim_pbc_n4_g1p00__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_pbc_n4_g1p00__quantized | quantized | 2 | 2 | selected | True | - |
| tfim_pbc_n4_g1p00__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_pbc_n4_g1p00__quantized | quantized | 3 | 1 | selected | True | - |
| tfim_pbc_n4_g1p00__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_pbc_n4_g1p00__quantized | quantized | 3 | 2 | selected | True | - |
| tfim_pbc_n4_g1p00__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_pbc_n6_g0p50__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_pbc_n6_g0p50__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_pbc_n6_g0p50__floating | floating | 2 | 2 | selected | False | 0,1,2 |
| tfim_pbc_n6_g0p50__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_pbc_n6_g0p50__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_pbc_n6_g0p50__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_pbc_n6_g0p50__floating | floating | 3 | 2 | selected | False | 0,1,2 |
| tfim_pbc_n6_g0p50__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_pbc_n6_g0p50__quantized | quantized | 2 | 1 | selected | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 2 | 2 | selected | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_pbc_n6_g0p50__quantized | quantized | 3 | 1 | selected | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 3 | 2 | selected | False | 1 |
| tfim_pbc_n6_g0p50__quantized | quantized | 3 | 2 | full | False | 1,2 |
| tfim_pbc_n6_g1p00__floating | floating | 2 | 1 | selected | False | 0,1 |
| tfim_pbc_n6_g1p00__floating | floating | 2 | 1 | full | False | 0,1 |
| tfim_pbc_n6_g1p00__floating | floating | 2 | 2 | selected | False | 0,1,2 |
| tfim_pbc_n6_g1p00__floating | floating | 2 | 2 | full | False | 0,1,2 |
| tfim_pbc_n6_g1p00__floating | floating | 3 | 1 | selected | False | 0,1 |
| tfim_pbc_n6_g1p00__floating | floating | 3 | 1 | full | False | 0,1 |
| tfim_pbc_n6_g1p00__floating | floating | 3 | 2 | selected | False | 0,1,2 |
| tfim_pbc_n6_g1p00__floating | floating | 3 | 2 | full | False | 0,1,2 |
| tfim_pbc_n6_g1p00__quantized | quantized | 2 | 1 | selected | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 2 | 1 | full | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 2 | 2 | selected | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 2 | 2 | full | False | 1,2 |
| tfim_pbc_n6_g1p00__quantized | quantized | 3 | 1 | selected | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 3 | 1 | full | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 3 | 2 | selected | False | 1 |
| tfim_pbc_n6_g1p00__quantized | quantized | 3 | 2 | full | False | 1,2 |
| square_patch_3x3__floating | floating | 2 | 1 | selected | True | - |
| square_patch_3x3__floating | floating | 2 | 1 | full | False | 1 |
| square_patch_3x3__floating | floating | 2 | 2 | selected | True | - |
| square_patch_3x3__floating | floating | 2 | 2 | full | False | 1,2 |
| square_patch_3x3__floating | floating | 3 | 1 | selected | True | - |
| square_patch_3x3__floating | floating | 3 | 1 | full | False | 1 |
| square_patch_3x3__floating | floating | 3 | 2 | selected | True | - |
| square_patch_3x3__floating | floating | 3 | 2 | full | False | 1,2 |
| square_patch_3x3__quantized | quantized | 2 | 1 | selected | True | - |
| square_patch_3x3__quantized | quantized | 2 | 1 | full | False | 1 |
| square_patch_3x3__quantized | quantized | 2 | 2 | selected | True | - |
| square_patch_3x3__quantized | quantized | 2 | 2 | full | False | 1,2 |
| square_patch_3x3__quantized | quantized | 3 | 1 | selected | True | - |
| square_patch_3x3__quantized | quantized | 3 | 1 | full | False | 1 |
| square_patch_3x3__quantized | quantized | 3 | 2 | selected | True | - |
| square_patch_3x3__quantized | quantized | 3 | 2 | full | False | 1,2 |
| triangular_patch_3x3__floating | floating | 2 | 1 | selected | False | 0,1 |
| triangular_patch_3x3__floating | floating | 2 | 1 | full | False | 0,1 |
| triangular_patch_3x3__floating | floating | 2 | 2 | selected | False | 0,1 |
| triangular_patch_3x3__floating | floating | 2 | 2 | full | False | 0,1,2 |
| triangular_patch_3x3__floating | floating | 3 | 1 | selected | False | 0,1 |
| triangular_patch_3x3__floating | floating | 3 | 1 | full | False | 0,1 |
| triangular_patch_3x3__floating | floating | 3 | 2 | selected | False | 0,1 |
| triangular_patch_3x3__floating | floating | 3 | 2 | full | False | 0,1,2 |
| triangular_patch_3x3__quantized | quantized | 2 | 1 | selected | False | 1 |
| triangular_patch_3x3__quantized | quantized | 2 | 1 | full | False | 1 |
| triangular_patch_3x3__quantized | quantized | 2 | 2 | selected | False | 1 |
| triangular_patch_3x3__quantized | quantized | 2 | 2 | full | False | 1,2 |
| triangular_patch_3x3__quantized | quantized | 3 | 1 | selected | False | 1 |
| triangular_patch_3x3__quantized | quantized | 3 | 1 | full | False | 1 |
| triangular_patch_3x3__quantized | quantized | 3 | 2 | selected | False | 1 |
| triangular_patch_3x3__quantized | quantized | 3 | 2 | full | False | 1,2 |
| honeycomb_patch_2x2__floating | floating | 2 | 1 | selected | False | 0 |
| honeycomb_patch_2x2__floating | floating | 2 | 1 | full | False | 0,1 |
| honeycomb_patch_2x2__floating | floating | 2 | 2 | selected | False | 0 |
| honeycomb_patch_2x2__floating | floating | 2 | 2 | full | False | 0,1,2 |
| honeycomb_patch_2x2__floating | floating | 3 | 1 | selected | False | 0 |
| honeycomb_patch_2x2__floating | floating | 3 | 1 | full | False | 0,1 |
| honeycomb_patch_2x2__floating | floating | 3 | 2 | selected | False | 0 |
| honeycomb_patch_2x2__floating | floating | 3 | 2 | full | False | 0,1,2 |
| honeycomb_patch_2x2__quantized | quantized | 2 | 1 | selected | True | - |
| honeycomb_patch_2x2__quantized | quantized | 2 | 1 | full | False | 1 |
| honeycomb_patch_2x2__quantized | quantized | 2 | 2 | selected | True | - |
| honeycomb_patch_2x2__quantized | quantized | 2 | 2 | full | False | 1,2 |
| honeycomb_patch_2x2__quantized | quantized | 3 | 1 | selected | True | - |
| honeycomb_patch_2x2__quantized | quantized | 3 | 1 | full | False | 1 |
| honeycomb_patch_2x2__quantized | quantized | 3 | 2 | selected | True | - |
| honeycomb_patch_2x2__quantized | quantized | 3 | 2 | full | False | 1,2 |
| nacl_coordination_shell__floating | floating | 2 | 1 | selected | True | - |
| nacl_coordination_shell__floating | floating | 2 | 1 | full | False | 1 |
| nacl_coordination_shell__floating | floating | 2 | 2 | selected | True | - |
| nacl_coordination_shell__floating | floating | 2 | 2 | full | False | 1,2 |
| nacl_coordination_shell__floating | floating | 3 | 1 | selected | True | - |
| nacl_coordination_shell__floating | floating | 3 | 1 | full | False | 1 |
| nacl_coordination_shell__floating | floating | 3 | 2 | selected | True | - |
| nacl_coordination_shell__floating | floating | 3 | 2 | full | False | 1,2 |
| nacl_coordination_shell__quantized | quantized | 2 | 1 | selected | True | - |
| nacl_coordination_shell__quantized | quantized | 2 | 1 | full | False | 1 |
| nacl_coordination_shell__quantized | quantized | 2 | 2 | selected | True | - |
| nacl_coordination_shell__quantized | quantized | 2 | 2 | full | False | 1,2 |
| nacl_coordination_shell__quantized | quantized | 3 | 1 | selected | True | - |
| nacl_coordination_shell__quantized | quantized | 3 | 1 | full | False | 1 |
| nacl_coordination_shell__quantized | quantized | 3 | 2 | selected | True | - |
| nacl_coordination_shell__quantized | quantized | 3 | 2 | full | False | 1,2 |

## discrepancy analysis

156 case(s) failed exact agreement after canonicalization by homological dimension.
156 discrepancy case(s) have zero bottleneck and Wasserstein distance, indicating convention-level differences such as zero-length bars.
0 discrepancy case(s) have a strictly positive diagram distance.
80 discrepancy case(s) include H0 endpoint hex mismatches in floating mode, driven by `gudhi` preserving float64 endpoints while `ripser` and `dionysus` round to float32-level values.
144 discrepancy case(s) include higher-dimensional zero-length bars reported by `gudhi` but omitted by `ripser` and `dionysus`.

| case_id | matrix_size | threshold | mismatch_dims |
| --- | --- | --- | --- |
| tfim_obc_n4_g0p50__floating__p2__h1__selected | 4 | selected | 0 |
| tfim_obc_n4_g0p50__floating__p2__h1__full | 4 | full | 0,1 |
| tfim_obc_n4_g0p50__floating__p2__h2__selected | 4 | selected | 0 |
| tfim_obc_n4_g0p50__floating__p2__h2__full | 4 | full | 0,1,2 |
| tfim_obc_n4_g0p50__floating__p3__h1__selected | 4 | selected | 0 |
| tfim_obc_n4_g0p50__floating__p3__h1__full | 4 | full | 0,1 |
| tfim_obc_n4_g0p50__floating__p3__h2__selected | 4 | selected | 0 |
| tfim_obc_n4_g0p50__floating__p3__h2__full | 4 | full | 0,1,2 |
| tfim_obc_n4_g0p50__quantized__p2__h1__full | 4 | full | 1 |
| tfim_obc_n4_g0p50__quantized__p2__h2__full | 4 | full | 1,2 |
| tfim_obc_n4_g0p50__quantized__p3__h1__full | 4 | full | 1 |
| tfim_obc_n4_g0p50__quantized__p3__h2__full | 4 | full | 1,2 |
| tfim_obc_n4_g1p00__floating__p2__h1__selected | 4 | selected | 0 |
| tfim_obc_n4_g1p00__floating__p2__h1__full | 4 | full | 0,1 |
| tfim_obc_n4_g1p00__floating__p2__h2__selected | 4 | selected | 0 |
| tfim_obc_n4_g1p00__floating__p2__h2__full | 4 | full | 0,1,2 |
| tfim_obc_n4_g1p00__floating__p3__h1__selected | 4 | selected | 0 |
| tfim_obc_n4_g1p00__floating__p3__h1__full | 4 | full | 0,1 |
| tfim_obc_n4_g1p00__floating__p3__h2__selected | 4 | selected | 0 |
| tfim_obc_n4_g1p00__floating__p3__h2__full | 4 | full | 0,1,2 |
| tfim_obc_n4_g1p00__quantized__p2__h1__full | 4 | full | 1 |
| tfim_obc_n4_g1p00__quantized__p2__h2__full | 4 | full | 1,2 |
| tfim_obc_n4_g1p00__quantized__p3__h1__full | 4 | full | 1 |
| tfim_obc_n4_g1p00__quantized__p3__h2__full | 4 | full | 1,2 |
| tfim_obc_n6_g0p50__floating__p2__h1__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g0p50__floating__p2__h1__full | 6 | full | 0,1 |
| tfim_obc_n6_g0p50__floating__p2__h2__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g0p50__floating__p2__h2__full | 6 | full | 0,1,2 |
| tfim_obc_n6_g0p50__floating__p3__h1__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g0p50__floating__p3__h1__full | 6 | full | 0,1 |
| tfim_obc_n6_g0p50__floating__p3__h2__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g0p50__floating__p3__h2__full | 6 | full | 0,1,2 |
| tfim_obc_n6_g0p50__quantized__p2__h1__selected | 6 | selected | 1 |
| tfim_obc_n6_g0p50__quantized__p2__h1__full | 6 | full | 1 |
| tfim_obc_n6_g0p50__quantized__p2__h2__selected | 6 | selected | 1 |
| tfim_obc_n6_g0p50__quantized__p2__h2__full | 6 | full | 1,2 |
| tfim_obc_n6_g0p50__quantized__p3__h1__selected | 6 | selected | 1 |
| tfim_obc_n6_g0p50__quantized__p3__h1__full | 6 | full | 1 |
| tfim_obc_n6_g0p50__quantized__p3__h2__selected | 6 | selected | 1 |
| tfim_obc_n6_g0p50__quantized__p3__h2__full | 6 | full | 1,2 |
| tfim_obc_n6_g1p00__floating__p2__h1__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g1p00__floating__p2__h1__full | 6 | full | 0,1 |
| tfim_obc_n6_g1p00__floating__p2__h2__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g1p00__floating__p2__h2__full | 6 | full | 0,1,2 |
| tfim_obc_n6_g1p00__floating__p3__h1__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g1p00__floating__p3__h1__full | 6 | full | 0,1 |
| tfim_obc_n6_g1p00__floating__p3__h2__selected | 6 | selected | 0,1 |
| tfim_obc_n6_g1p00__floating__p3__h2__full | 6 | full | 0,1,2 |
| tfim_obc_n6_g1p00__quantized__p2__h1__selected | 6 | selected | 1 |
| tfim_obc_n6_g1p00__quantized__p2__h1__full | 6 | full | 1 |
| tfim_obc_n6_g1p00__quantized__p2__h2__selected | 6 | selected | 1 |
| tfim_obc_n6_g1p00__quantized__p2__h2__full | 6 | full | 1,2 |
| tfim_obc_n6_g1p00__quantized__p3__h1__selected | 6 | selected | 1 |
| tfim_obc_n6_g1p00__quantized__p3__h1__full | 6 | full | 1 |
| tfim_obc_n6_g1p00__quantized__p3__h2__selected | 6 | selected | 1 |
| tfim_obc_n6_g1p00__quantized__p3__h2__full | 6 | full | 1,2 |
| tfim_pbc_n4_g0p50__floating__p2__h1__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g0p50__floating__p2__h1__full | 4 | full | 0,1 |
| tfim_pbc_n4_g0p50__floating__p2__h2__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g0p50__floating__p2__h2__full | 4 | full | 0,1,2 |
| tfim_pbc_n4_g0p50__floating__p3__h1__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g0p50__floating__p3__h1__full | 4 | full | 0,1 |
| tfim_pbc_n4_g0p50__floating__p3__h2__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g0p50__floating__p3__h2__full | 4 | full | 0,1,2 |
| tfim_pbc_n4_g0p50__quantized__p2__h1__full | 4 | full | 1 |
| tfim_pbc_n4_g0p50__quantized__p2__h2__full | 4 | full | 1,2 |
| tfim_pbc_n4_g0p50__quantized__p3__h1__full | 4 | full | 1 |
| tfim_pbc_n4_g0p50__quantized__p3__h2__full | 4 | full | 1,2 |
| tfim_pbc_n4_g1p00__floating__p2__h1__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g1p00__floating__p2__h1__full | 4 | full | 0,1 |
| tfim_pbc_n4_g1p00__floating__p2__h2__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g1p00__floating__p2__h2__full | 4 | full | 0,1,2 |
| tfim_pbc_n4_g1p00__floating__p3__h1__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g1p00__floating__p3__h1__full | 4 | full | 0,1 |
| tfim_pbc_n4_g1p00__floating__p3__h2__selected | 4 | selected | 0,1 |
| tfim_pbc_n4_g1p00__floating__p3__h2__full | 4 | full | 0,1,2 |
| tfim_pbc_n4_g1p00__quantized__p2__h1__full | 4 | full | 1 |
| tfim_pbc_n4_g1p00__quantized__p2__h2__full | 4 | full | 1,2 |
| tfim_pbc_n4_g1p00__quantized__p3__h1__full | 4 | full | 1 |
| tfim_pbc_n4_g1p00__quantized__p3__h2__full | 4 | full | 1,2 |
| tfim_pbc_n6_g0p50__floating__p2__h1__selected | 6 | selected | 0,1 |
| tfim_pbc_n6_g0p50__floating__p2__h1__full | 6 | full | 0,1 |
| tfim_pbc_n6_g0p50__floating__p2__h2__selected | 6 | selected | 0,1,2 |
| tfim_pbc_n6_g0p50__floating__p2__h2__full | 6 | full | 0,1,2 |
| tfim_pbc_n6_g0p50__floating__p3__h1__selected | 6 | selected | 0,1 |
| tfim_pbc_n6_g0p50__floating__p3__h1__full | 6 | full | 0,1 |
| tfim_pbc_n6_g0p50__floating__p3__h2__selected | 6 | selected | 0,1,2 |
| tfim_pbc_n6_g0p50__floating__p3__h2__full | 6 | full | 0,1,2 |
| tfim_pbc_n6_g0p50__quantized__p2__h1__selected | 6 | selected | 1 |
| tfim_pbc_n6_g0p50__quantized__p2__h1__full | 6 | full | 1 |
| tfim_pbc_n6_g0p50__quantized__p2__h2__selected | 6 | selected | 1 |
| tfim_pbc_n6_g0p50__quantized__p2__h2__full | 6 | full | 1,2 |
| tfim_pbc_n6_g0p50__quantized__p3__h1__selected | 6 | selected | 1 |
| tfim_pbc_n6_g0p50__quantized__p3__h1__full | 6 | full | 1 |
| tfim_pbc_n6_g0p50__quantized__p3__h2__selected | 6 | selected | 1 |
| tfim_pbc_n6_g0p50__quantized__p3__h2__full | 6 | full | 1,2 |
| tfim_pbc_n6_g1p00__floating__p2__h1__selected | 6 | selected | 0,1 |
| tfim_pbc_n6_g1p00__floating__p2__h1__full | 6 | full | 0,1 |
| tfim_pbc_n6_g1p00__floating__p2__h2__selected | 6 | selected | 0,1,2 |
| tfim_pbc_n6_g1p00__floating__p2__h2__full | 6 | full | 0,1,2 |
| tfim_pbc_n6_g1p00__floating__p3__h1__selected | 6 | selected | 0,1 |
| tfim_pbc_n6_g1p00__floating__p3__h1__full | 6 | full | 0,1 |
| tfim_pbc_n6_g1p00__floating__p3__h2__selected | 6 | selected | 0,1,2 |
| tfim_pbc_n6_g1p00__floating__p3__h2__full | 6 | full | 0,1,2 |
| tfim_pbc_n6_g1p00__quantized__p2__h1__selected | 6 | selected | 1 |
| tfim_pbc_n6_g1p00__quantized__p2__h1__full | 6 | full | 1 |
| tfim_pbc_n6_g1p00__quantized__p2__h2__selected | 6 | selected | 1 |
| tfim_pbc_n6_g1p00__quantized__p2__h2__full | 6 | full | 1,2 |
| tfim_pbc_n6_g1p00__quantized__p3__h1__selected | 6 | selected | 1 |
| tfim_pbc_n6_g1p00__quantized__p3__h1__full | 6 | full | 1 |
| tfim_pbc_n6_g1p00__quantized__p3__h2__selected | 6 | selected | 1 |
| tfim_pbc_n6_g1p00__quantized__p3__h2__full | 6 | full | 1,2 |
| square_patch_3x3__floating__p2__h1__full | 9 | full | 1 |
| square_patch_3x3__floating__p2__h2__full | 9 | full | 1,2 |
| square_patch_3x3__floating__p3__h1__full | 9 | full | 1 |
| square_patch_3x3__floating__p3__h2__full | 9 | full | 1,2 |
| square_patch_3x3__quantized__p2__h1__full | 9 | full | 1 |
| square_patch_3x3__quantized__p2__h2__full | 9 | full | 1,2 |
| square_patch_3x3__quantized__p3__h1__full | 9 | full | 1 |
| square_patch_3x3__quantized__p3__h2__full | 9 | full | 1,2 |
| triangular_patch_3x3__floating__p2__h1__selected | 9 | selected | 0,1 |
| triangular_patch_3x3__floating__p2__h1__full | 9 | full | 0,1 |
| triangular_patch_3x3__floating__p2__h2__selected | 9 | selected | 0,1 |
| triangular_patch_3x3__floating__p2__h2__full | 9 | full | 0,1,2 |
| triangular_patch_3x3__floating__p3__h1__selected | 9 | selected | 0,1 |
| triangular_patch_3x3__floating__p3__h1__full | 9 | full | 0,1 |
| triangular_patch_3x3__floating__p3__h2__selected | 9 | selected | 0,1 |
| triangular_patch_3x3__floating__p3__h2__full | 9 | full | 0,1,2 |
| triangular_patch_3x3__quantized__p2__h1__selected | 9 | selected | 1 |
| triangular_patch_3x3__quantized__p2__h1__full | 9 | full | 1 |
| triangular_patch_3x3__quantized__p2__h2__selected | 9 | selected | 1 |
| triangular_patch_3x3__quantized__p2__h2__full | 9 | full | 1,2 |
| triangular_patch_3x3__quantized__p3__h1__selected | 9 | selected | 1 |
| triangular_patch_3x3__quantized__p3__h1__full | 9 | full | 1 |
| triangular_patch_3x3__quantized__p3__h2__selected | 9 | selected | 1 |
| triangular_patch_3x3__quantized__p3__h2__full | 9 | full | 1,2 |
| honeycomb_patch_2x2__floating__p2__h1__selected | 8 | selected | 0 |
| honeycomb_patch_2x2__floating__p2__h1__full | 8 | full | 0,1 |
| honeycomb_patch_2x2__floating__p2__h2__selected | 8 | selected | 0 |
| honeycomb_patch_2x2__floating__p2__h2__full | 8 | full | 0,1,2 |
| honeycomb_patch_2x2__floating__p3__h1__selected | 8 | selected | 0 |
| honeycomb_patch_2x2__floating__p3__h1__full | 8 | full | 0,1 |
| honeycomb_patch_2x2__floating__p3__h2__selected | 8 | selected | 0 |
| honeycomb_patch_2x2__floating__p3__h2__full | 8 | full | 0,1,2 |
| honeycomb_patch_2x2__quantized__p2__h1__full | 8 | full | 1 |
| honeycomb_patch_2x2__quantized__p2__h2__full | 8 | full | 1,2 |
| honeycomb_patch_2x2__quantized__p3__h1__full | 8 | full | 1 |
| honeycomb_patch_2x2__quantized__p3__h2__full | 8 | full | 1,2 |
| nacl_coordination_shell__floating__p2__h1__full | 7 | full | 1 |
| nacl_coordination_shell__floating__p2__h2__full | 7 | full | 1,2 |
| nacl_coordination_shell__floating__p3__h1__full | 7 | full | 1 |
| nacl_coordination_shell__floating__p3__h2__full | 7 | full | 1,2 |
| nacl_coordination_shell__quantized__p2__h1__full | 7 | full | 1 |
| nacl_coordination_shell__quantized__p2__h2__full | 7 | full | 1,2 |
| nacl_coordination_shell__quantized__p3__h1__full | 7 | full | 1 |
| nacl_coordination_shell__quantized__p3__h2__full | 7 | full | 1,2 |

## reproducibility notes
- Run the full harness from WSL/Linux with `make all`.
- The pinned Python environment is recorded in `requirements.txt` and `artifacts/environment/pip_freeze.txt`.
- Every input point cloud and distance matrix is saved under `artifacts/inputs/` with SHA-256 hashes in the benchmark manifests.
- Raw library outputs are saved per case under `artifacts/cases/`.
- Canonicalized interval tables are saved per case under `artifacts/canonical_tables/`.
- Machine-readable summaries are saved under `artifacts/summary/` and `artifacts/discrepancies/`.
- For Dionysus, the exact conformance path uses condensed distance-matrix input; no approximation modes are enabled in any library.
