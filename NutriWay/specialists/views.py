from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from .forms import SubscriptionPlanForm , GeneralPlanForm ,SubscriberMealForm, SubscriberPlanForm ,SubscriberMealFormSet
from .models import SubscriptionPlan , Generalplan ,SubscriberMeal,SubscriberPlan,MealCheck
from accounts.models import Specialist , Certificate , Person
from django.contrib import messages
from users.models import Subscription , ProgressReport,GeneralPlanPurchase
from datetime import date
from datetime import datetime
from django.db.models import Avg ,  Count,  Sum , Case,When,Value,IntegerField , Q
from django.utils.timezone import now
from calendar import month_name
import json
from collections import defaultdict
from django.core.paginator import Paginator

def create_subscription_plan(request: HttpRequest):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
    except Specialist.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.", "alert-danger")
        return redirect('core:home_view')

    if request.method == "POST":
        form = SubscriptionPlanForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                subscription_plan = form.save(commit=False)
                subscription_plan.specialist = specialist
                subscription_plan.save()
                messages.success(request, "Subscription plan created successfully.", "alert-success")
                return redirect("core:home_view")
            except Exception as e:
                messages.error(request, "Failed to save the subscription plan.", "alert-danger")
        else:
            messages.error(request, "Please correct the errors in the form.", "alert-danger")
    else:
        form = SubscriptionPlanForm()

    return render(request, 'specialists/create_subscription_plan.html', {'form': form, 'plan_type_choices': SubscriptionPlan.PlanType.choices})





def create_general_plan(request: HttpRequest):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
    except Specialist.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.", "alert-danger")
        return redirect('core:home_view')

    if request.method == "POST":
        form = GeneralPlanForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                general_plan = form.save(commit=False)
                general_plan.specialist = specialist
                general_plan.save()
                messages.success(request, "General plan created successfully.", "alert-success")
                return redirect("core:home_view")
            except Exception as e:
                messages.error(request, "Failed to create general plan.", "alert-danger")
        else:
            messages.error(request, f"Please correct the errors in the form.", "alert-danger")
    else:
        form = GeneralPlanForm()

    return render(request, 'specialists/create_general_plan.html', {'form': form , 'plan_type_choices': Generalplan.PlanType.choices})



def list_general_plan(request):
    filter_value = request.GET.get('filter')
    type_filter = request.GET.get('type')

    plans = Generalplan.objects.select_related('specialist__user')

    if type_filter:
        plans = plans.filter(plan_type=type_filter)

    if filter_value == "low":
        plans = plans.order_by("price")
    elif filter_value == "high":
        plans = plans.order_by("-price")

    paginator = Paginator(plans, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, 'specialists/list_general_plan.html', {
        "plans": page_obj,
        "page_obj": page_obj,
        "selected_filter": filter_value,
        "selected_type": type_filter,
        "planType": Generalplan.PlanType.choices,
    })


def list_subscription_plan(request: HttpRequest):
    type_filter = request.GET.get('type')
    gender_filter = request.GET.get('gender')
    sort_filter = request.GET.get('sort')

    plans = SubscriptionPlan.objects.select_related('specialist__user')

    if type_filter:
        plans = plans.filter(plan_type=type_filter)

    if gender_filter:
        plans = plans.filter(specialist__gender=gender_filter)

    if sort_filter == "low":
        plans = plans.order_by("price")
    elif sort_filter == "high":
        plans = plans.order_by("-price")

    paginator = Paginator(plans, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "planType": SubscriptionPlan.PlanType.choices,
        "genderChoices": Specialist.GenderChoices.choices,
        "duration_choices": SubscriptionPlan.DurationChoices.choices,
        "selected_type": type_filter,
        "selected_gender": gender_filter,
        "selected_sort": sort_filter,
    }

    return render(request, 'specialists/list_subscription_plan.html', context)


def my_plans(request: HttpRequest):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
    except Specialist.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.", "alert-danger")
        return redirect('core:home_view')

    plans = SubscriptionPlan.objects.filter(specialist=specialist).annotate(
        subscriber_count=Count('subscription', filter=Q(subscription__status__in=['active']))
    )
    general_plans = Generalplan.objects.filter(specialist=specialist)
    paginator = Paginator(plans, 3)  
    page_number = request.GET.get("Subscription_page")
    page_obj = paginator.get_page(page_number)

    general_paginator = Paginator(general_plans, 3)
    general_page_number = request.GET.get("general_page")
    general_page_obj = general_paginator.get_page(general_page_number)


    

    return render(request, 'specialists/my_plans.html', {
        'specialist': specialist,
        'plans': page_obj,
        'page_obj': page_obj,
        'general_plans': general_page_obj,
        'general_page_obj': general_page_obj,
    })



def all_specialists(request: HttpRequest):
    gender = request.GET.get('gender')
    specialty = request.GET.get('specialty')
    sort = request.GET.get('sort')

    specialists = Specialist.objects.annotate(average_rating=Avg('reviews__rating')).filter(specialistrequest__status='approved')

    for specialist in specialists:
        born = specialist.birth_date
        today = date.today()
        specialist.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    if gender:
        specialists = specialists.filter(gender=gender)

    if specialty:
        specialists = specialists.filter(specialty=specialty)

    if sort == 'high rating':
        specialists = specialists.order_by('-average_rating')
    elif sort == 'low rating':
        specialists = specialists.order_by('average_rating')

    paginator = Paginator(specialists, 6) 
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        'specialists': page_obj,
        'page_obj': page_obj,
        'genderChoices': Specialist.GenderChoices.choices,
        'specialtyChoices': Specialist.SpecialtyChoices.choices,
        'selected_gender': gender,
        'selected_specialty': specialty,
        'selected_sort': sort,
    }

    return render(request, 'specialists/specialists_list.html', context)

def specialist_detail(request:HttpRequest , specialist_id):
    try:
        specialist = Specialist.objects.get(id=specialist_id)
        certificate = Certificate.objects.filter(specialist=specialist)
        plans = SubscriptionPlan.objects.filter(specialist=specialist)
    except Specialist.DoesNotExist:
        return redirect("core:home_view")
    return render(request, 'specialists/specialist_detail.html', {'specialist': specialist,'certificate': certificate,'plans': plans, "DurationChoices":SubscriptionPlan.DurationChoices.choices})

def specialist_subscriptions(request: HttpRequest, plan_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
        subscription_plan = SubscriptionPlan.objects.get(id=plan_id, specialist=specialist)
    except (Specialist.DoesNotExist, SubscriptionPlan.DoesNotExist):
        messages.error(request, "You are not authorized to access this page.", "alert-danger")
        return redirect('core:home_view')

    plan = SubscriptionPlan.objects.get(id=plan_id)

    filter_status = request.GET.get('status', 'all')


    subscriptions = Subscription.objects.filter(
        subscription_plan=subscription_plan,
        status__in=[Subscription.StatusChoices.ACTIVE, Subscription.StatusChoices.EXPIRED]
    )


    if filter_status == 'active':
        subscriptions = subscriptions.filter(status=Subscription.StatusChoices.ACTIVE)
    elif filter_status == 'expired':
        subscriptions = subscriptions.filter(status=Subscription.StatusChoices.EXPIRED)

    subscriptions = subscriptions.annotate(
        status_order=Case(
            When(status=Subscription.StatusChoices.ACTIVE, then=Value(0)),
            When(status=Subscription.StatusChoices.EXPIRED, then=Value(1)),
            output_field=IntegerField()
        )
    ).order_by('status_order', '-start_date')

    today = datetime.now().date()
    for subscription in subscriptions:
        if today > subscription.end_date and subscription.status != Subscription.StatusChoices.EXPIRED:
            subscription.status = Subscription.StatusChoices.EXPIRED
            subscription.save()

    paginator = Paginator(subscriptions, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'specialists/view_subscriptions.html',
        {
            'plan': plan,
            'subscriptions': page_obj,
            'subscription_plan': subscription_plan,
            'page_obj': page_obj,
            'filter_status': filter_status,
        }
    )


def create_subscriber_plan(request: HttpRequest, subscription_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        print(f'subscription_id:{subscription_id}, specialist:{request.user}')
        specialist = Specialist.objects.get(user=request.user)
        subscription = Subscription.objects.get(id=subscription_id, subscription_plan__specialist=specialist)
    except (Specialist.DoesNotExist, Subscription.DoesNotExist):
        messages.error(request, "You are not authorized.", "alert-danger")
        return redirect('core:home_view')

    if request.method == "POST":
        plan_name = request.POST.get('name')
        plan_description = request.POST.get('description')

        if not plan_name or not plan_description:
            messages.error(request, "Plan name and description are required.", "alert-danger")
            return redirect(request.path)

        subscriber_plan = SubscriberPlan.objects.create(
            specialist=specialist,
            name=plan_name,
            description=plan_description
        )

        subscription.subscriber_plan = subscriber_plan
        subscription.save()

        meals = []
        i = 0
        while True:
            day_number = request.POST.get(f'day_number-{i}')
            meal_type = request.POST.get(f'meal_type-{i}')
            meal_description = request.POST.get(f'description-{i}')
            meal_calorie = request.POST.get(f'meal_calorie-{i}')

            if day_number and meal_type and meal_description and meal_calorie:
                meals.append(SubscriberMeal(
                    subscriber_plan=subscriber_plan,
                    day_number=day_number,
                    meal_type=meal_type,
                    description=meal_description,meal_calorie=meal_calorie
                ))
                i += 1
            else:
                break

        if meals:
            SubscriberMeal.objects.bulk_create(meals)

        messages.success(request, "Subscriber plan and meals created successfully.", "alert-success")
        return redirect('users:subscription_detail',subscription_id)

    return render(request, 'specialists/create_subscriber_plan.html', {'subscription': subscription,"subscriberMeal": SubscriberMeal.MealTypeChoices.choices})





def edit_subscriber_plan(request: HttpRequest, plan_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
        subscriber_plan = SubscriberPlan.objects.get(id=plan_id, specialist=specialist)
    except (Specialist.DoesNotExist, SubscriberPlan.DoesNotExist):
        messages.error(request, "You are not authorized to edit this plan.", "alert-danger")
        return redirect('core:home_view')

    if request.method == "POST":
        old_meals = SubscriberMeal.objects.filter(subscriber_plan=subscriber_plan)
        for meal in old_meals:
            delete_flag = request.POST.get(f"delete-{meal.id}")
            if delete_flag == "1":
                meal.delete()
            else:
                day_number = request.POST.get(f"day_number-{meal.id}")
                meal_type = request.POST.get(f"meal_type-{meal.id}")
                description = request.POST.get(f"description-{meal.id}")
                meal_calorie = request.POST.get(f"meal_calorie-{meal.id}")

                if day_number and meal_type and description and meal_calorie:
                    meal.day_number = day_number
                    meal.meal_type = meal_type
                    meal.description = description
                    meal.meal_calorie = meal_calorie
                    meal.save()

        i = 0
        while True:
            day_number = request.POST.get(f'day_number-new-{i}')
            meal_type = request.POST.get(f'meal_type-new-{i}')
            description = request.POST.get(f'description-new-{i}')
            meal_calorie = request.POST.get(f'meal_calorie-new-{i}')

            if day_number and meal_type and description and meal_calorie:
                SubscriberMeal.objects.create(subscriber_plan=subscriber_plan,day_number=day_number,meal_type=meal_type,description=description,meal_calorie=meal_calorie)
                i += 1
            else:
                break

        messages.success(request, "Meals updated successfully.", "alert-success")
        return redirect('specialists:edit_subscriber_plan',plan_id)

    meals = SubscriberMeal.objects.filter(subscriber_plan=subscriber_plan)
    subscription = Subscription.objects.get(subscriber_plan=subscriber_plan)
    return render(request, 'specialists/edit_subscriber_plan.html', {'subscriber_plan': subscriber_plan,'meals': meals,'subscription':subscription , "subscriberMeal": SubscriberMeal.MealTypeChoices.choices
})




def add_comment(request: HttpRequest, subscription_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
        subscription = Subscription.objects.get(id=subscription_id, subscription_plan__specialist=specialist)
    except (Specialist.DoesNotExist, Subscription.DoesNotExist) as e:
        messages.error(request, "You are not authorized to access this page.", "alert-danger")

        return redirect('core:home_view')

    progress_reports = ProgressReport.objects.filter(subscription=subscription).order_by('date')

    if request.method == "POST":
        progress_id = request.POST.get('progress_id')
        comment = request.POST.get('specialist_comment')

        try:
            progress_report = ProgressReport.objects.get(id=progress_id, subscription=subscription)
        except ProgressReport.DoesNotExist:
            return redirect('core:home_view')

        if not progress_report.specialist_comment:
            progress_report.specialist_comment = comment
            progress_report.save()

        return redirect('users:view_progress', subscription_id=subscription_id)

    return render(request, 'users/view_progress.html', {'subscription': subscription, 'progress_reports': progress_reports})



def delete_subscription(request: HttpRequest, subscription_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this page.", "alert-danger")
        return redirect('accounts:login_view')

    try:
        specialist = Specialist.objects.get(user=request.user)
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.subscription_plan.specialist != specialist:
            messages.error(request, "You are not authorized to cancel this subscriber.", "alert-danger")
            return redirect('core:home_view')

        subscription.status = 'cancelled'
        subscription.save()

        messages.success(request, "Subscriber has been successfully cancelled.", "alert-success")

    except (Specialist.DoesNotExist, Subscription.DoesNotExist):
        messages.error(request, "Subscriber not found or you are not authorized.", "alert-danger")

    return redirect('specialists:my_plans')



def view_subscriber_plan(request:HttpRequest, subscription_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in.", "alert-danger")
        return redirect('accounts:login_view')
    
    try:
        specialist = Specialist.objects.get(user=request.user)
        subscription = Subscription.objects.get(id=subscription_id)

        if subscription.subscription_plan.specialist != specialist:
            messages.error(request, "You are not authorized to view this subscription.", "alert-danger")
            return redirect('core:home_view')

    except (Specialist.DoesNotExist, Subscription.DoesNotExist):
        messages.error(request, "Subscription not found or you are not authorized.", "alert-danger")
        return redirect('core:home_view')
    
    meals = SubscriberMeal.objects.filter(subscriber_plan=subscription.subscriber_plan)
    today = date.today()
    checks = MealCheck.objects.filter(subscription=subscription, date=today)

    check_status = []
    for meal in meals:
        status = None
        for check in checks:
            if check.subscriber_meal_id == meal.id:
                status = check.is_checked
                break
        check_status.append((meal, status))
    return render(request, 'specialists/view_subscriber_plan.html', {'subscription': subscription,'person': subscription.person,'check_status': check_status ,'today': today})


def show_certificate_specialization(request, specialist_id):
    specialist = Specialist.objects.get(pk=specialist_id)
    return render(request, 'specialists/show_specialization_certificate_certificate.html', {'specialist': specialist})
def show_certificate(request, specialist_id):
    specialist = Specialist.objects.get(pk=specialist_id)
    certificates = specialist.Certificates.all()
    return render(request, 'specialists/show_certificates.html', {'specialist': specialist ,'certificates':certificates})


def specialist_dashboard(request, specialist_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access the dashboard.", "alert-danger")
        return redirect("accounts:login_view")

    try:
        specialist = Specialist.objects.get(id=specialist_id)
    except Specialist.DoesNotExist:
        messages.error(request, "Specialist not found.", "alert-danger")
        return redirect("core:home_view")

    if not hasattr(request.user, 'specialist') or request.user != specialist.user:
        messages.error(request, "You are not authorized to view this dashboard.", "alert-danger")
        return redirect("core:home_view")

    subscriptions = Subscription.objects.filter(subscription_plan__specialist=specialist, status="active")
    subscriber_plans = SubscriptionPlan.objects.filter(specialist=specialist)
    general_plans = Generalplan.objects.filter(specialist=specialist)
    general_plan_purchases = GeneralPlanPurchase.objects.filter(general_plan__specialist=specialist)

    total_subscribers = subscriptions.count()

    total_earnings = 0
    monthly_earnings = defaultdict(int)
    subscriber_counts = defaultdict(int)

    duration_map = {
        '1_month': 1,
        '3_months': 3,
        '6_months': 6,
        '12_months': 12
    }

    for sub in subscriptions:
        months = duration_map.get(sub.duration, 1)
        earnings = sub.subscription_plan.price * months
        total_earnings += earnings

        if sub.start_date:
            month_label = sub.start_date.strftime("%B")
            monthly_earnings[month_label] += earnings
            subscriber_counts[month_label] += 1

    for purchase in general_plan_purchases:
        total_earnings += purchase.general_plan.price
        if purchase.purchase_date:
            month_label = purchase.purchase_date.strftime("%B")
            monthly_earnings[month_label] += purchase.general_plan.price

    all_months = list(month_name)[1:]
    monthly_earnings_data = {month: monthly_earnings.get(month, 0) for month in all_months}
    subscriber_counts_data = {month: subscriber_counts.get(month, 0) for month in all_months}

    person_ids = subscriptions.values_list('person_id', flat=True).distinct()
    persons = Person.objects.filter(id__in=person_ids)

    male_count = persons.filter(gender__iexact='male').count()
    female_count = persons.filter(gender__iexact='female').count()
    total_persons = male_count + female_count

    male_percentage = round((male_count / total_persons) * 100, 2) if total_persons else 0
    female_percentage = round((female_count / total_persons) * 100, 2) if total_persons else 0

    context = {
        'specialist': specialist,
        'total_subscribers': total_subscribers,
        'subscription_plan_count': subscriber_plans.count(),
        'general_plan_count': general_plans.count(),
        'total_earnings': total_earnings,
        'male_percentage': male_percentage,
        'female_percentage': female_percentage,
        'monthly_earnings': json.dumps(monthly_earnings_data),
        'subscriber_counts': json.dumps(subscriber_counts_data),
    }

    return render(request, 'specialists/dashboard.html', context)

def general_plan_detail_view(request: HttpRequest, plan_id: int):
    try:
        plan = Generalplan.objects.get(id=plan_id)
    except Generalplan.DoesNotExist:
        messages.error(request, "General plan not found.", "alert-danger")
        return redirect("core:home_view")
    return render(request, 'specialists/general_plan_detail.html', {'plan': plan})

def subscription_plan_detail_view (request:HttpRequest , plan_id:int):
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Subscription plan not found.", "alert-danger")
        return redirect("core:home_view")
    
    is_subscribed = False
    if request.user.is_authenticated:
        is_subscribed = plan.subscription_set.filter(person__user=request.user, status='active').exists()
    return render(request, 'specialists/supscription_plan_detail.html', {'plan': plan , "duration_choices": SubscriptionPlan.DurationChoices.choices,'is_subscribed': is_subscribed,})