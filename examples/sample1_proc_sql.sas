/* Example 1: PROC SQL — joins, aggregation, filtering. */
%let min_amount = 1000;

proc sql;
   create table work.high_value as
   select c.customer_id,
          c.region,
          sum(o.amount) as total_amount,
          count(*) as order_count
   from work.customers as c
   inner join work.orders as o
      on c.customer_id = o.customer_id
   where o.amount >= &min_amount
   group by c.customer_id, c.region
   having calculated total_amount > 5000
   order by total_amount desc;
quit;
