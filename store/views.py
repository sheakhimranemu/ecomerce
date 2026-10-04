from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Product, Category, Order

def home(request):
    query = request.GET.get('q')
    category_slug = request.GET.get('category')
    
    products = Product.objects.filter(is_available=True)
    categories = Category.objects.all()

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if query:
        products = products.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    return render(request, 'store/home.html', {
        'products': products,
        'categories': categories,
        'query': query,
        'selected_category': category_slug
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        quantity = int(request.POST.get('quantity', 1))
        
        total_price = product.price * quantity
        
        Order.objects.create(
            name=name,
            phone=phone,
            address=address,
            product=product,
            quantity=quantity,
            total_price=total_price
        )
        messages.success(request, 'আপনার অর্ডারটি সফলভাবে গ্রহণ করা হয়েছে! আমরা শীঘ্রই যোগাযোগ করব।')
        return redirect('product_detail', pk=product.pk)

    return render(request, 'store/product_detail.html', {'product': product})
