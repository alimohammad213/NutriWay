from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from specialists.models import SubscriptionPlan, Generalplan
from accounts.models import Person
from django.core.mail import send_mail
from payments.models import Payment
import logging
from users.models import GeneralPlanPurchase
from users.views import subscription_to_plan , Subscription
from django.contrib import messages

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


def start_checkout_subscription(request : HttpRequest, plan_id : int) -> HttpResponse:
    # Check if the user is authenticated and has a profile
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view') 

    try:
        # Retrieve the subscription plan
        plan = SubscriptionPlan.objects.get(id=plan_id)
    except SubscriptionPlan.DoesNotExist:
        logger.error(f"Plan with ID {plan_id} does not exist")
        return HttpResponse("Invalid plan ID", status=400)


    # Create a Stripe checkout session
    try:
            duration_key = request.GET.get('duration') 
            DURATION_MULTIPLIERS = {
                '1_month': 1,
                '3_months': 3,
                '6_months': 6,
                '12_months': 12
            }
            multiplier = DURATION_MULTIPLIERS.get(duration_key, 1)
            total_price = int(plan.price * multiplier * 100)
            session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'sar',
                    'product_data': {
                        'name': f'{dict(SubscriptionPlan.DurationChoices.choices).get(duration_key, "")} Plan - {plan.name}',
                    },
                    'unit_amount': total_price, 
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'http://127.0.0.1:8000/success/?plan_id={plan.id}&duration={duration_key}', 
            cancel_url='http://127.0.0.1:8000/cancel/',
            customer_email=request.user.email,
            metadata={
                "plan_id": plan.id,
                "user_id": request.user.id,
                'duration': duration_key
            }
        )    
    except stripe.StripeError as e:
        logger.error(f"Stripe error: {e}")
        messages.error(request, "There was an error processing your payment. Please try again.", "alert-danger")
        return redirect("payments:subscription_summary", plan_id=plan_id)

    #Redirect directly to Stripe
    return redirect(session.url)



#This payment success for subscription plan
def payment_success(request : HttpRequest) -> HttpResponse:
    duration_key = request.GET.get('duration')  # Retrieve duration from request
    duration_label = dict(SubscriptionPlan.DurationChoices.choices).get(duration_key, 'N/A')  # Map to label
    try:
        # Retrieve the plan ID from the request query parameters
        plan_id = request.GET.get('plan_id')
        if not plan_id:
            logger.error("Plan ID is missing in the request")
            return HttpResponse("Plan ID is required", status=400)
        plan = SubscriptionPlan.objects.get(id=plan_id)

        # Calculate total price based on duration
        DURATION_MULTIPLIERS = {
            '1_month': 1,
            '3_months': 3,
            '6_months': 6,
            '12_months': 12
        }
        multiplier = DURATION_MULTIPLIERS.get(duration_key, 1)
        total_price = plan.price * multiplier
    except SubscriptionPlan.DoesNotExist:
        logger.error(f"Plan with ID {plan_id} does not exist")
        return HttpResponse("Invalid plan ID", status=400)
    
    try:
        person = Person.objects.get(user=request.user)
    except Person.DoesNotExist:
        username = getattr(request.user, 'username', 'Unknown')
        logger.error(f"No Person found for user {username}")
        return HttpResponse("User profile error", status=400)

    # Create payment record
    try:
        Payment.objects.create(
            person=person,
            specialist=plan.specialist,
            subscription_plan=plan,
            general_plan=None,  # No general plan for subscription payments
            amount=total_price,
            payment_method='visa',
            status='Paid',
            selected_duration=duration_key 
        )
        
        subscription = subscription_to_plan(request, plan_id=int(plan_id), duration=duration_key)


    except Exception as e:
        logger.error(f"Error creating payment record: {e}")
        return HttpResponse("Error creating payment record", status=500)

    # Send confirmation email
    try:
        send_mail(
            subject='NutriWay - Payment Confirmation',
            message=(
                f"Hi {person.user.first_name},\n\n"
                f"Your payment of {total_price} SAR for the {duration_key.replace('_', ' ')} {plan.name} plan has been received.\n"
                f"Your specialist is {plan.specialist.user.username}.\n\n"
                f"Subscription Plan: {plan.name}\n"
                f"Description: {plan.description}\n"
                f"Thank you for subscribing to NutriWay!"
                f"\n\nBest regards,\n"
                f"NutriWay Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[person.user.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Error sending confirmation email: {e}")

    # Render the success page
    return render(request, 'payments/subscription_success.html', {
        'plan': plan,
        'amount': plan.price,
        'duration': duration_label,
    })



#This payment cancel for subscription plan
def payment_cancel(request : HttpRequest) -> HttpResponse:
    # Handle payment cancellation
    return render(request, 'payments/subscription_cancel.html')



#This start checkout for general plan
def start_checkout_general(request: HttpRequest, plan_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect("accounts:login_view")

    try:
        plan = Generalplan.objects.get(id=plan_id)
    except Generalplan.DoesNotExist:
        return HttpResponse("General plan not found", status=404)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'sar',
                'product_data': {
                    'name': f"General Plan - {plan.name}",
                },
                'unit_amount': int(round(plan.price * 100)),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=f'http://127.0.0.1:8000/general-success/?plan_id={plan.id}',
        cancel_url='http://127.0.0.1:8000/general-cancel/',
        customer_email=request.user.email,
        metadata={
            "plan_id": plan.id,
            "user_id": request.user.id,
            "plan_type": "general"
        }
    )

    return redirect(session.url)



#This payment success for general plan
logger = logging.getLogger(__name__)
def payment_success_general(request: HttpRequest) -> HttpResponse:
    plan_id = request.GET.get('plan_id')

    if not plan_id:
        logger.error("Missing general plan ID in success URL")
        return HttpResponse("Missing plan ID", status=400)

    try:
        plan = Generalplan.objects.get(id=plan_id)
    except Generalplan.DoesNotExist:
        logger.error(f"General plan with ID {plan_id} does not exist")
        return HttpResponse("General plan not found", status=404)

    # Use request.user if logged in, or fall back to anonymous handling if needed
    user = request.user
    if not user.is_authenticated:
        return HttpResponse("Please log in to complete this action.", status=401)

    # Get the person (linked to user)
    try:
        person = Person.objects.get(user=user)
    except Person.DoesNotExist:
        username = getattr(request.user, 'username', 'Unknown')
        logger.error(f"No Person profile for user {username}")
        return HttpResponse("User profile not found", status=400)

    # Check for duplicate payment
    existing_payment = Payment.objects.filter(
        person=person,
        general_plan=plan,  
        status='Paid',
        amount=plan.price
    ).first()

    if existing_payment:
        logger.info(f"Duplicate payment avoided for general plan ID {plan_id}")
    else:
        # Save payment record
        try:
            Payment.objects.create(
                person=person,
                specialist=plan.specialist,
                general_plan=plan,
                subscription_plan=None, # No subscription plan for general plans
                amount=plan.price,
                payment_method='visa',  # Assuming 'visa' is the default payment method
                status='Paid'
            )
            GeneralPlanPurchase.objects.create(
                person = person,
                general_plan = plan
            )
        except Exception as e:
            logger.error(f"Error saving general payment: {e}")
            return HttpResponse("Error saving payment", status=500)

    # Send confirmation email
    try:
        send_mail(
            subject="NutriWay - General Plan Purchase Confirmation",
            message=(
                f"Hi {person.user.first_name},\n\n"
                f"Thank you for purchasing the general plan: {plan.name}.\n\n"
                f"Price of {plan.price} SAR has been charged to your account.\n\n"
                f"You can now access the plan file or await specialist instructions.\n\n"
                f"Best regards,\nNutriWay Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,  
            recipient_list=[person.user.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Error sending general plan confirmation email: {e}")

    # Render the success page
    return render(request, 'payments/generalplan_success.html', {
        'plan': plan,
        'amount': plan.price,
    })


#This payment cancel for general plan
def payment_cancel_general(request : HttpRequest) -> HttpResponse:
    # Handle payment cancellation
    return render(request, 'payments/generalplan_cancel.html')



#This is the summary logic for subscription plan
# Preview before payment
def subscription_summary(request : HttpRequest, plan_id : int) -> HttpResponse:
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)

        if not request.user.is_authenticated:
            request.session['redirect_after_login'] = request.build_absolute_uri()
            messages.error(request, "You must be logged in to access this page.", "alert-danger")
            return redirect("accounts:login_view")
        
        if hasattr(request.user, 'specialist') or hasattr(request.user, 'director') or request.user.is_staff:
            messages.error(request, "You are not authorized to subscribe to plans.", "alert-danger")
            return redirect("specialists:list_subscription_plan")

        person = Person.objects.get(user=request.user)

        
        if Subscription.objects.filter(person=person, subscription_plan=plan, status='active').exists():
            messages.warning(request, "You are already subscribed to this plan.", "alert-warning")
            return redirect("users:my_plans_view")
        
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        DURATION_MULTIPLIERS = {
        '1_month': 1,
        '3_months': 3,
        '6_months': 6,
        '12_months': 12
        }
        
        duration_key = request.GET.get('duration')
        duration_label = dict(SubscriptionPlan.DurationChoices.choices).get(duration_key or '', 'Not selected')
        multiplier = DURATION_MULTIPLIERS.get(duration_key, 1) # default to 1 month
        total_price = plan.price * multiplier 
        
        context = {
            'plan': plan,
            'specialist_name': plan.specialist.user.get_full_name() or plan.specialist.user.username,
            'duration': duration_label,
            'duration_key': duration_key,
            'total_price': total_price,
            'payment_methods': ['Visa', 'Mastercard'],  
        }

        return render(request, 'payments/subscription_summary.html', context)
    
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Subscription plan not found.", "alert-danger")
    except Person.DoesNotExist:
        messages.error(request, "You must complete your profile before subscribing.", "alert-danger")

    return redirect("specialists:list_subscription_plan")



#This summary logic for general plan
# Preview before payment

def generalplan_summary(request : HttpRequest, plan_id : int) -> HttpResponse:
    if not request.user.is_authenticated:
        request.session['redirect_after_login'] = request.build_absolute_uri()
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect("accounts:login_view")
    try:
        plan = Generalplan.objects.get(id=plan_id)


        
        if hasattr(request.user, 'specialist') or hasattr(request.user, 'director') or request.user.is_staff:
            messages.error(request, "You are not authorized to pay plans.", "alert-danger")
            return redirect("specialists:list_general_plan")

        person = Person.objects.get(user=request.user)

        
        context = {
            'plan': plan,
            'specialist_name': plan.specialist.user.get_full_name() or plan.specialist.user.username,
            'payment_methods': ['Visa', 'Mastercard'],
        }
        return render(request, 'payments/generalplan_summary.html', context)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Subscription plan not found.", "alert-danger")
    except Person.DoesNotExist:
        messages.error(request, "You must complete your profile before subscribing.", "alert-danger")

    return redirect("specialists:list_subscription_plan")