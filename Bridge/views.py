from django.shortcuts import render

# Create your views here.
def Request(request):
    return render (request, 'Bridge/request.html', )