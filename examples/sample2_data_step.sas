/* Example 2: DATA step transformations + PROC MEANS aggregation. */
data work.enriched;
   set work.sales;
   where region ne 'TEST';
   margin = revenue - cost;
   if margin > 0 then status = 'PROFIT';
   else status = 'LOSS';
   tax = revenue * 0.07;
   keep customer_id region revenue margin status tax;
run;

proc means data=work.enriched mean sum n std;
   class region;
   var revenue margin;
   output out=work.region_summary;
run;
