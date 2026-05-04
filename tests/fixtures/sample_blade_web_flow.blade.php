<form action="/orders/store" method="post">
  <button type="submit">Create Order</button>
</form>

<a href="/orders">Orders</a>

@include('orders.summary')
<livewire:orders.table />
