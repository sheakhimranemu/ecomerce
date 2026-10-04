from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Category, Product, Order, OrderItem, Coupon, Review

# Helper function for session-based cart
def get_cart(request):
    return request.session.get('cart', {})

def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True

def home(request):
    categories = Category.objects.all()
    products = Product.objects.all()
    query = request.GET.get('q')
    selected_category = request.GET.get('category')

    if query:
        products = products.filter(title__icontains=query)
    if selected_category:
        products = products.filter(category__slug=selected_category)

    return render(request, 'store/home.html', {
        'categories': categories,
        'products': products,
        'query': query,
        'selected_category': selected_category
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST' and 'review_submit' in request.POST:
        name = request.POST.get('reviewer_name')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        Review.objects.create(product=product, name=name, rating=rating, comment=comment)
        messages.success(request, 'Review submitted successfully!')
        return redirect('product_detail', pk=pk)

    return render(request, 'store/product_detail.html', {'product': product})

def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = get_cart(request)
    product_id = str(pk)
    qty = int(request.POST.get('quantity', 1))

    if product_id in cart:
        cart[product_id] += qty
    else:
        cart[product_id] = qty

    save_cart(request, cart)
    messages.success(request, f'Added "{product.title}" to your cart.')
    return redirect('cart_detail')

def cart_detail(request):
    cart = get_cart(request)
    cart_items = []
    total = 0

    for product_id, qty in cart.items():
        try:
            prod = Product.objects.get(id=product_id)
            subtotal = prod.price * qty
            total += subtotal
            cart_items.append({
                'product': prod,
                'quantity': qty,
                'subtotal': subtotal
            })
        except Product.DoesNotExist:
            continue

    # Coupon Handling
    discount = 0
    applied_coupon = request.session.get('coupon_code')
    coupon_obj = None

    if request.method == 'POST' and 'apply_coupon' in request.POST:
        code = request.POST.get('coupon_code', '').strip()
        try:
            coupon_obj = Coupon.objects.get(code__iexact=code, active=True)
            request.session['coupon_code'] = coupon_obj.code
            messages.success(request, f'Coupon "{coupon_obj.code}" applied successfully!')
            return redirect('cart_detail')
        except Coupon.DoesNotExist:
            messages.error(request, 'Invalid or expired coupon code.')

    if applied_coupon:
        try:
            coupon_obj = Coupon.objects.get(code__iexact=applied_coupon, active=True)
            discount = (total * coupon_obj.discount_percentage) / 100
        except Coupon.DoesNotExist:
            request.session['coupon_code'] = None

    grand_total = total - discount if total > discount else 0

    return render(request, 'store/cart.html', {
        'cart_items': cart_items,
        'total': total,
        'discount': discount,
        'grand_total': grand_total,
        'applied_coupon': applied_coupon
    })

def update_cart(request, pk):
    cart = get_cart(request)
    product_id = str(pk)
    action = request.POST.get('action')

    if product_id in cart:
        if action == 'increase':
            cart[product_id] += 1
        elif action == 'decrease':
            cart[product_id] -= 1
            if cart[product_id] <= 0:
                del cart[product_id]
        elif action == 'remove':
            del cart[product_id]

    save_cart(request, cart)
    return redirect('cart_detail')

def checkout(request):
    cart = get_cart(request)
    if not cart:
        messages.warning(request, 'Your cart is empty.')
        return redirect('home')

    cart_items = []
    total = 0
    for product_id, qty in cart.items():
        try:
            prod = Product.objects.get(id=product_id)
            subtotal = prod.price * qty
            total += subtotal
            cart_items.append({'product': prod, 'quantity': qty, 'subtotal': subtotal})
        except Product.DoesNotExist:
            continue

    applied_coupon = request.session.get('coupon_code')
    discount = 0
    coupon_obj = None
    if applied_coupon:
        try:
            coupon_obj = Coupon.objects.get(code__iexact=applied_coupon, active=True)
            discount = (total * coupon_obj.discount_percentage) / 100
        except Coupon.DoesNotExist:
            pass

    grand_total = max(0, total - discount)

    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        payment_method = request.POST.get('payment_method', 'COD')
        transaction_id = request.POST.get('transaction_id', '')

        # Check stock availability
        with transaction.atomic():
            for item in cart_items:
                if item['product'].stock < item['quantity']:
                    messages.error(request, f"Sorry, '{item['product'].title}' is out of stock or does not have enough stock available.")
                    return redirect('cart_detail')

            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=name,
                phone=phone,
                address=address,
                payment_method=payment_method,
                transaction_id=transaction_id if payment_method in ['bKash', 'Nagad'] else '',
                coupon=coupon_obj,
                discount_amount=discount,
                total_price=grand_total,
                status='Pending'
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['product'].price,
                    quantity=item['quantity']
                )
                # Auto decrement stock
                item['product'].stock -= item['quantity']
                if item['product'].stock == 0:
                    item['product'].is_available = False
                item['product'].save()

            # Clear cart and coupon session
            request.session['cart'] = {}
            request.session['coupon_code'] = None

            messages.success(request, f'Order #{order.id} placed successfully!')
            return redirect('order_invoice', pk=order.id)

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'discount': discount,
        'grand_total': grand_total
    })

def order_invoice(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, 'store/invoice.html', {'order': order})

@login_required
def profile(request):
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/profile.html', {'orders': user_orders})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'store/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'store/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully.')
    return redirect('home')
