from django.shortcuts import render

def test_low_words_view(request):
    """
    Test view for the 'Not Enough Words' warning page.
    """
    return render(request, 'vocabulary/test_low_words.html')
