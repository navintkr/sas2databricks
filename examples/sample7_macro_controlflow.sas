/* Example 7: macro control flow -- %IF/%THEN/%DO/%ELSE and an iterative %DO loop. */
%macro revenue_report(grain=, periods=);
   %if &grain = region %then %do;
      proc means data=work.enriched sum;
         class region;
         var revenue;
      run;
   %end;
   %else %if &grain = product %then %do;
      proc means data=work.enriched sum;
         class product;
         var revenue;
      run;
   %end;
   %else %do;
      proc means data=work.enriched sum;
         var revenue;
      run;
   %end;

   %do p = 1 %to &periods;
      proc means data=work.enriched mean;
         var revenue;
      run;
   %end;
%mend revenue_report;
