/* Example 6: DATA step arrays + an iterative DO loop (deterministic unroll). */
data work.scored;
   set work.responses;
   array q{3} q1-q3;
   array s{3} s1-s3;
   do i = 1 to 3;
      s{i} = q{i} * 10;
   end;
   total_score = s1 + s2 + s3;
run;
