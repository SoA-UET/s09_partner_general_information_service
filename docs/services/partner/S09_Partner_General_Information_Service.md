# Telcenter Partner - **S09: Partner General Information Service**

Introducing the series of Telcenter Engineering.

Telcenter, on the surface, is a semi-automated telecom services call center -
it is a web app that offers telecommunication services consultation. People
are serviced by the AI Agent, and they will be forwarded to in-person
consultants if the AI detected down mood, rage, or that it could not answer
the question itself given a pre-fed ground truth database. Now, we are
designing this as microservices. Telcenter Core would act as the main backend
for the end-user interface, and it consists of multiple microservices.
Telcenter Partner is another system that is deployed separately on each of
the telecom partner's servers, and it is responsible for taking up forwarded
conversations and continuing them with the real persons in-charge. Together,
one Core and several Partner systems cooperate to deliver the best customer
experience, while lowering cost dramatically, with the help of automated AI
responses.

The general deployment and communication topology is like this:

    Core <---(Internet)---> (Partner_1, Partner_2..., Partner_N)

The users' inquiries and answers to those are primarily in Vietnamese.

Now, you are designing the **S09: Partner General Information Service** service, in Python.
This service is inside the **Telcenter Partner** system.

Here are the peer services that the **S09: Partner General Information Service** service may interact with. We will come up
with the flow of this service itself later.

- **Core's Partner Management Service (S07)**: This service is deployed on the Core system and manages partner connections. S07 calls S09 via HTTP to retrieve partner information, verify connections, and get partner capabilities.
- **Authorized Core Gateway Service**: This Core Gateway acts as the gateway on the Core system. Core Gateway calls S09 via RabbitMQ to query Core service endpoint information when Partner services need to communicate with Core.
- **Partner Portal**: This is the administrative web interface for Telcenter Partner system. Partner administrators use this portal to manage their partner information, capabilities, and system configuration. The Partner Portal calls S09 via HTTP REST API (H25 and H26) to view and update partner information, upload logo, manage capabilities, and configure Core connection. All partner self-management operations are initiated from this portal.

## A Note on API Transport Layers

The APIs of the services (including this one
and the peers) might be based on HTTP and/or
RabbitMQ transport protocols. One service might
also exposes multiple APIs of different kinds.

HTTP is mostly used in APIs that are exposed
to the frontend web apps, though it occasionally
is used for internal communication between
microservices, too. HTTP APIs are somewhat
RESTful (it is CRUD, stateless, versioned,
and HATEOAS, but it need not follow
Code-on-Demand requirements.)

For APIs that are based on RabbitMQ transport,
each API usually demands two queues, the
requests queue and the responses queue. The
caller would send requests into the former queue
and expect the responses to come out from the
latter. Exceptions will be explicitly noted.
The default queue names will be specified for
each such API. The queue names should be configurable
via `.env`, too.

## Peer Service APIs

Note that the base URL to call the services
must be specified via `.env`. Construct
a `.env.example` file for that.

[A12b](../../api_groups/A12.md)

[H11](../../api_groups/H11.md)

## The Flow

### Main Flow: Connect to Telcenter Core

1. Admin Telcenter Partner obtains the Core API URL
   and API key. He then enters
   all this into a frontend.

2. The frontend calls API H26 to test the connection
   to Telcenter Core with the given credentials.

3. The backend (S09), upon receiving that H26 request,
   calls API H11 to verify
   the connection to Telcenter Core.

4. Once verified, S09 returns `partner_id` to the frontend
   (obtained from H11).

5. The frontend calls API H25
   to save the Core connection information,
   including `core_url`, `api_key`, and `partner_id`.

5. Later, S09 would offer the core connection information (API
   URL, Partner ID and API key) to other services via A12 API.

## This Service's APIs

### **Partner Portal**

[H25](../../api_groups/H25.md)

[H26](../../api_groups/H26.md)

## Technology

- Python
- Use `uv` as the virtual environment and package manager.
- Multithreaded logic should be used for performance, since this
  component relies a lot on other services, which means the API calls
  to those services take up very much time. So this service is I/O bound.
  Note that, using multithreading to emulate async operations is very
  important - but do NOT use `async` and `await` in Python - that would
  be a mess!

- The class `MessageQueueService` must be used for RabbitMQ communication (which internally
  use `pika`).

  The class is [located in this file](../../../app/services/MessageQueueService.py).

  An example of using this class [is given here](../../MessageQueueService-usage-example.py).

  Also, for multithreading, only use the scheme in that file.
  Any other use of multithreading, if necessary, must strictly
  look for hazards - use locks and other synchronization primitives
  where appropriate.

- If this service needs to expose HTTP API(s), use Flask.

- The program entry point is [in this file](../../../app/__main__.py).

## Database Schema

Database: `telcenter_partner_partner`

### Table: `information`

Lưu trữ thông tin kết nối của các Partner telecom. Đây là bảng chính cho việc quản lý partner.

Bảng này chỉ có một bản ghi duy nhất, đại diện cho chính Partner này.

Các cột:

- `_id` (ObjectId, Primary Key): Auto-generated
- `partner_id` (string): ID of this partner, assigned by Core
- `name` (string): Tên nhà mạng (VD: Vinaphone, Viettel)
- `api_key` (string): API key để xác thực API
- `core_url` (string): Endpoint API của hệ thống Core
- `created_at` (datetime): Thời gian tạo
- `updated_at` (datetime): Thời gian cập nhật gần nhất
