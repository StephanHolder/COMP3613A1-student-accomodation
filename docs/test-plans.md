# Test plans: Student Accommodation

Three plans cover the app at different levels. Each one says what is tested, how, and what counts as a pass.

| Plan | Level | Tool | Where it lives |
| --- | --- | --- | --- |
| Unit test plan | One module at a time, repositories mocked | pytest | `tests/unit/` |
| Integration test plan | Routes + services + repositories + database | pytest, FastAPI TestClient | `tests/integration/` |
| API test plan | The deployed JSON API, as a client sees it | Postman collection | `postman/` |
| User acceptance test plan | A person using the pages, against the wireframes | Manual, with a results table | this file |

Run everything from the project root (`pytest`: 296 tests), or one level at a time (`pytest -m unit`: 137, `pytest -m integration`: 159).

---

## 1. Unit test plan

**Goal.** Prove each business rule in isolation, so a failure points at one module.

**Approach.**
- Services are tested with **mocked repositories** (`MagicMock(spec=...)`). No database is created and no network is used.
- Models are plain objects built in memory. Each test sets up only the state it needs, then asserts on the returned object or the exception.
- Errors are asserted by type: `NotFoundError` (404), `ForbiddenError` (403), `ConflictError` (409), `ValueError` (422).

**Out of scope.** SQL, templates and HTTP. Those belong to the integration plan.

| Module | Rules covered | Tests | File |
| --- | --- | --- | --- |
| `ListingService` | Landlord-only posting; required text fields; price must be plain digits and positive; zero security fee allowed; at most five photos; image type and size checks; uploaded files removed when a later photo fails; admin approve/reject; rejection needs a reason; a decided listing cannot be decided again; public listing must be Verified; search price rules (min above max, non-numeric, negative, NaN/inf) | 40 | `test_listing_service.py` |
| `ApplicationService` | Students only; listing must exist, be Verified and available; no applying to your own listing; no duplicate active application; request details only from Applied and by the owning landlord; student details validated (name, digits-only positive age, purpose); accept only from Info Submitted, only if available and no active booking; accept creates a booking Awaiting Payment; decline needs a reason and a valid status | 41 | `test_application_service.py` |
| `BookingService` | Payment total = rent + security fee; payment records method, amount, paid flag and date; blank method refused; only the booked student pays; cannot pay twice; move-out date must be after the start date and only from Confirmed; completion only from Notice Given, by the listing owner, frees the listing and completes the application; who may view a booking | 24 | `test_booking_service.py` |
| `ReviewService` | One review per booking; only after Completed; only the booked student; rating 1 to 5 (boundaries 1 and 5, values 0, 6 and -1 refused); comment required; paging inputs validated | 17 | `test_review_service.py` |
| `AuthService` | Token issued for valid credentials with the user id and role; wrong password and unknown user rejected; registration hashes the password and creates a student | 4 | `test_auth_service.py` |
| Utilities | Pagination (page count, first/middle/last page, zero results, zero limit, page gaps); password hashing round trip; token claims; token signed with another key is invalid | 11 | `test_utilities.py` |
| **Total** | | **137** | |

**Pass criteria.** All 137 tests pass (`pytest -m unit`), and deliberately breaking a rule (for example removing the duplicate-application check) makes at least one test fail.

---

## 2. Integration test plan

**Goal.** Prove the layers work together: route, service, repository and database, including authorization and the three named workflows from start to finish.

**Approach.**
- Every test gets a **fresh in-memory SQLite database**. The app's `get_session` dependency is overridden, so the real `database.db` and the Render Postgres database are never touched.
- Requests go through FastAPI's `TestClient`. The API is called with bearer tokens; the HTML pages are called with the sign-in cookie, exactly as a browser would.
- Factories create users, listings, applications, bookings and reviews directly in the database, so a test starts from the exact state it needs.
- The standard cast is two students (bob, fred), two landlords, and an admin.

| Suite | What it proves | Tests | File |
| --- | --- | --- | --- |
| Authentication | Register (201, duplicates 409, invalid input 422), login returns a token, wrong credentials 401, current user, missing/garbage/non-bearer token 401, user list is admin-only (401 / 403 / 200) | 18 | `test_api_auth.py` |
| Listings | Posting a listing (201, role checks 403, no token 401, invalid price 422); admin verification (approve, reject with reason, decided twice 409, non-admin 403); pending queue (order, five per page); public search (Verified only, filters for address, room type, price and amenities, five per page, page past the end); landlord's own listings, two per page | 38 | `test_api_listings.py` |
| Workflows | The whole chain: post, verify, apply, request details, submit details, accept, pay, move out, complete, review. Plus the negative path of every step: wrong role 403, wrong owner 403, wrong state 409, bad input 422, unknown id 404, reviews paged five at a time newest first with the overall average | 53 | `test_api_workflows.py` |
| HTML pages | Sign in and out, cookie handling, 401 pages for signed-out visitors, role checks on forms, public search and detail pages, reviewer login shown on reviews, the decline reason shown to the student, and the three workflows driven through the real forms with 303 redirects | 25 | `test_html_views.py` |
| Repositories | Search filters and ordering, page clamping, pending-queue order, update only changes status and reason, in-progress booking rules, payment confirmation, uniqueness (one booking per application, one review per booking, unique usernames), review average over all rows | 25 | `test_repositories.py` |
| **Total** | | **159** | |

**Main functionality covered.** Every route that a named workflow uses, for each role that may and may not call it.

**Pass criteria.** All 159 tests pass (`pytest -m integration`). The full lifecycle tests (`test_full_lifecycle_from_posting_to_review` and `test_all_three_workflows_through_the_pages`) pass.

---

## 3. API test plan (Postman)

**Goal.** Check the JSON API from the outside, the way a client would, including REST conventions: nouns for resources, `POST` returns 201, `PUT` updates, and correct 401, 403, 404, 409 and 422 codes.

**Approach.** `postman/StudentAccommodation.postman_collection.json` holds 61 requests in four folders: authentication, then one folder per workflow. Each request has a test script (89 assertions in total). Folders run in order, because later requests reuse the listing, application and booking created earlier (stored as collection variables). Each run creates new data, so the collection can be run repeatedly.

**Run it.** Start the app (`python manage.py init`, then `python manage.py run`), import the collection and the `Local` environment into Postman, and use the Collection Runner. The base URL defaults to `http://localhost:5000`.

**Pass criteria.** The collection run shows 61 requests, 89 assertions, 0 failed.

---

## 4. User acceptance test (UAT) plan

**Goal.** Confirm a real person can complete each named workflow using only the pages, and that the pages match the wireframes.

**Setup.** Run `python manage.py init` (seeds the data) and `python manage.py run`, then open http://localhost:5000. You need an internet connection, because the pages load their styling from a CDN. Use three separate browser sessions so the sign-ins do not interfere: Chrome (landlord), a Chrome private window (admin), and Edge (student).

| Role | Username | Password |
| --- | --- | --- |
| Landlord | landlord | landlordpass |
| Admin | admin | adminpass |
| Student | bob | bobpass |
| Student | fred | fredpass |

**How to record.** For each task, follow the steps, compare the result with the success criteria and the wireframe, then mark **Pass** or **Fail** and note anything unexpected in the results table in section 5.

### Workflow 1: Post listing detail for verification (Landlord, Admin)

| ID | Task | Steps | Expected results | Wireframe |
| --- | --- | --- | --- | --- |
| UAT-01 | Open the posting form | Sign in as **landlord**. Choose **Post a listing** in the menu. | The form shows Address, Room type, Amenities, Price, Security fee, Pictures and a **Submit for verification** button. | `Post-Listing-details.png` |
| UAT-02 | Post a valid listing | Enter an address, room type, amenities, price `2500` and security fee `500`. Add one or two pictures. Choose **Submit for verification**. | "Listing submitted successfully!" appears. **Current listings** shows the new listing with status **Pending**. | `Post-Listing-details.png`, `landlord-dashboard_current-listings-current-applications.png` |
| UAT-03 | Refuse an invalid price | Open **Post a listing** again. Fill the other fields. Try to type `abc` in Price, then leave Price empty and submit. Then enter `0` as the price and submit. | Letters cannot be typed into Price. An empty Price stops the form with the browser's "Please fill out this field". A price of `0` shows "Price must be positive and security fee cannot be negative." No listing is created. | `Post-Listing-details.png` |
| UAT-04 | Admin sees the queue | In the second browser, sign in as **admin**. Choose **Review pending listings**. | The queue shows the new listing, with its address, price, security fee, room type, amenities and pictures, and **Approve** and **Reject** controls. | `Verify-listing.png` |
| UAT-05 | Reject needs a reason | Choose **Reject** with the reason box empty. Then enter a reason and choose **Reject** again. | The first attempt is stopped by the browser (the reason is required). The second shows "Listing decision submitted successfully." As landlord, **Current listings** shows **Rejected** with the reason. | `Verify-listing.png` |
| UAT-06 | Approve a listing | Post a second listing as landlord. As admin, choose **Pending listings**, then **Approve**. | The listing disappears from the queue. Signed out or as a student, it appears in **Search results**. | `Verify-listing.png`, `browse-search-listings.png` |

### Workflow 2: Apply to listed accommodation (Student)

| ID | Task | Steps | Expected results | Wireframe |
| --- | --- | --- | --- | --- |
| UAT-07 | Find accommodation | Sign in as **bob**. Choose **Find accommodation**. Filter by location, a price range and a room type. Choose **View listing**. | Only Verified listings that match the filters appear, five per page, with **Previous** and **Next**. The detail page shows address, photos, price, security fee, availability, rating and reviews. | `browse-search-listings.png`, `View-Listing-Details_View-Reviews.png` |
| UAT-08 | Apply | On the approved listing, enter a preferred start date and choose **Apply**. | "Your application was successfully sent." **My applications** shows the listing with status **Applied**. | `Apply-page_Applied-page.png` |
| UAT-09 | Duplicate application blocked | Open the same listing and try to apply again. | A message says there is already an active application. No second application appears. | `Apply-page_Applied-page.png` |
| UAT-10 | Landlord requests details | As landlord, open **Current listings**, find the application and choose **Request details**. As bob, open **My applications**. | The landlord sees "Application details were requested from the student." Bob's application shows **Info Requested** with fields for Full name, Age and Purpose of stay. | `landlord-dashboard_current-listings-current-applications.png`, `Student-details-submission.png` |
| UAT-11 | Student submits details | As bob, enter a name, an age (digits only) and a purpose, then choose **Submit requested details**. | "Your requested details were submitted." Status becomes **Info Submitted**. Letters cannot be typed into Age. An age of `0` is refused with "Student age must be a positive integer." | `Student-details-submission.png` |
| UAT-12 | Landlord accepts | As landlord, review the details, set **Decision** to **Accept**, and choose **Submit decision**. | "Application accepted and booking created." Bob's application shows status **Awaiting Payment** with the **Pay security fee and first month** button. | `Landlord-application_landlord-details_decline.png` |
| UAT-13 | Landlord declines with a reason | As **fred**, apply to another Verified listing and submit details. As landlord, set **Decision** to **Decline** and choose **Submit decision** with no reason, then again with a reason. | Without a reason: "Decline reason must be provided when declining an application." With a reason: "Application declined." Fred's **My applications** shows status **Declined** and the **Decline reason**. | `Landlord-application_landlord-details_decline.png` |
| UAT-14 | Pay | As bob, choose **Pay security fee and first month**, pick a payment method and choose **Submit payment**. | "Payment submitted successfully." The booking shows **Confirmed**. The total paid is rent plus security fee. The listing is now unavailable and cannot be applied to. | `Apps-and-Books_Payment_Details-submission.png` |

### Workflow 3: Submit review of completed stay (Student)

| ID | Task | Steps | Expected results | Wireframe |
| --- | --- | --- | --- | --- |
| UAT-15 | Give move-out notice | As bob, on the confirmed booking, enter a move-out date after the start date and choose **Submit move-out notice**. | "Move-out notice submitted." Status becomes **Notice Given**. A date on or before the start date is refused with "Move-out date must be after the booking start date." | `Move-out-notice.png` |
| UAT-16 | Landlord completes the stay | As landlord, open **Current listings** and choose **Mark as completed** on the booking. | "Booking marked as completed." The listing is available again for new applications. | `Landlord-Bookings.png` |
| UAT-17 | Submit a review | As bob, open **My applications** and choose **Submit review**. Pick a rating from 1 to 5, write a review, and submit. | "Your review was submitted." The review button is no longer offered for that booking. | `review-form.png` |
| UAT-18 | Review appears on the listing | Open the reviewed listing's detail page. | The review shows the reviewer's login (`bob`), the rating, the written review and the date. The listing's average rating includes it. | `View-Listing-Details_View-Reviews.png` |
| UAT-19 | Reviews list | Open the seeded listing at **31 Market Street**. | Its reviews appear newest first with reviewer logins `bob` and `fred`, five per page, with the average rating shown. | `View-Listing-Details_View-Reviews.png` |

### Access and session

| ID | Task | Steps | Expected results | Wireframe |
| --- | --- | --- | --- | --- |
| UAT-20 | Role protection | Signed in as **bob**, open `/admin/listings/pending` in the address bar. | A "Sign in required" page appears. No pending listings are shown. | none |
| UAT-21 | Sign out | Choose **Logout**, then try to open **My applications**. | **Logout** returns to the sign-in page. Opening **My applications** afterwards shows "Sign in required". | none |

### Not built

**Edit listing details** (`Edit-listing-details.png`) was designed but not built. A rejected listing is corrected by posting a new listing, and the report records this decision.

---

## 5. UAT results (completed by the tester)

Complete this table while running the scenarios above. Do not fill it in beforehand.

Tester: ____________________  Date: ____________  Browser(s): ____________________

| ID | Result (Pass / Fail) | What happened, and anything unexpected |
| --- | --- | --- |
| UAT-01 | | |
| UAT-02 | | |
| UAT-03 | | |
| UAT-04 | | |
| UAT-05 | | |
| UAT-06 | | |
| UAT-07 | | |
| UAT-08 | | |
| UAT-09 | | |
| UAT-10 | | |
| UAT-11 | | |
| UAT-12 | | |
| UAT-13 | | |
| UAT-14 | | |
| UAT-15 | | |
| UAT-16 | | |
| UAT-17 | | |
| UAT-18 | | |
| UAT-19 | | |
| UAT-20 | | |
| UAT-21 | | |
