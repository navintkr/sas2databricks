/* Example 3: PROC FORMAT, a macro, and a report — exercises the LLM-assisted path. */
proc format;
   value region_fmt
      1 = 'North'
      2 = 'South'
      3 = 'East'
      4 = 'West'
      other = 'Unknown';
   value $grade_fmt
      'A' = 'Excellent'
      'B' = 'Good'
      other = 'Needs Review';
run;

%macro summarize(ds=, var=);
   proc means data=&ds mean max min;
      var &var;
   run;
%mend summarize;

proc report data=work.enriched nowd;
   column region revenue margin;
   define region / group;
   title 'Regional Performance';
run;
