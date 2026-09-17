# ZAP Scanning Report

ZAP by [Checkmarx](https://checkmarx.com/).


## Summary of Alerts

| Risk Level | Number of Alerts |
| --- | --- |
| High | 0 |
| Medium | 3 |
| Low | 0 |
| Informational | 1 |




## Insights

| Level | Reason | Site | Description | Statistic |
| --- | --- | --- | --- | --- |
| Low | Warning |  | ZAP warnings logged - see the zap.log file for details | 1    |
| Info | Informational | http://host.docker.internal:3000 | Percentage of responses with status code 2xx | 100 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with content type application/javascript | 58 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with content type application/xml | 3 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with content type text/css | 3 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with content type text/html | 31 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with content type text/plain | 3 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with method GET | 96 % |
| Info | Informational | http://host.docker.internal:3000 | Percentage of endpoints with method POST | 3 % |
| Info | Informational | http://host.docker.internal:3000 | Count of total endpoints | 29    |
| Info | Informational | http://host.docker.internal:3000 | Percentage of slow responses | 3 % |







## Alerts

| Name | Risk Level | Number of Instances |
| --- | --- | --- |
| Absence of Anti-CSRF Tokens | Medium | 2 |
| CSP: script-src unsafe-inline | Medium | Systemic |
| CSP: style-src unsafe-inline | Medium | Systemic |
| Storable and Cacheable Content | Informational | Systemic |




## Alert Detail



### [ Absence of Anti-CSRF Tokens ](https://www.zaproxy.org/docs/alerts/10202/)



##### Medium (Low)

### Description

No Anti-CSRF tokens were found in a HTML submission form.
A cross-site request forgery is an attack that involves forcing a victim to send an HTTP request to a target destination without their knowledge or intent in order to perform an action as the victim. The underlying cause is application functionality using predictable URL/form actions in a repeatable way. The nature of the attack is that CSRF exploits the trust that a web site has for a user. By contrast, cross-site scripting (XSS) exploits the trust that a user has for a web site. Like XSS, CSRF attacks are not necessarily cross-site, but they can be. Cross-site request forgery is also known as CSRF, XSRF, one-click attack, session riding, confused deputy, and sea surf.

CSRF attacks are effective in a number of situations, including:
    * The victim has an active session on the target site.
    * The victim is authenticated via HTTP auth on the target site.
    * The victim is on the same local network as the target site.

CSRF has primarily been used to perform an action against a target site using the victim's privileges, but recent techniques have been discovered to disclose information by gaining access to the response. The risk of information disclosure is dramatically increased when the target site is vulnerable to XSS, because XSS can be used as a platform for CSRF, allowing the attack to operate within the bounds of the same-origin policy.

* URL: http://host.docker.internal:3000/register
  * Node Name: `http://host.docker.internal:3000/register`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form class="space-y-5" noValidate="" method="post">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "nickname" "password" "phone" ].`
* URL: http://host.docker.internal:3000/register
  * Node Name: `http://host.docker.internal:3000/register ()(nickname,password,phone)`
  * Method: `POST`
  * Parameter: ``
  * Attack: ``
  * Evidence: `<form class="space-y-5" noValidate="" method="post">`
  * Other Info: `No known Anti-CSRF token [anticsrf, CSRFToken, __RequestVerificationToken, csrfmiddlewaretoken, authenticity_token, OWASP_CSRFTOKEN, anoncsrf, csrf_token, _csrf, _csrfSecret, __csrf_magic, CSRF, _token, _csrf_token, _csrfToken] was found in the following HTML form: [Form 1: "nickname" "password" "phone" ].`


Instances: 2

### Solution

Phase: Architecture and Design
Use a vetted library or framework that does not allow this weakness to occur or provides constructs that make this weakness easier to avoid.
For example, use anti-CSRF packages such as the OWASP CSRFGuard.

Phase: Implementation
Ensure that your application is free of cross-site scripting issues, because most CSRF defenses can be bypassed using attacker-controlled script.

Phase: Architecture and Design
Generate a unique nonce for each form, place the nonce into the form, and verify the nonce upon receipt of the form. Be sure that the nonce is not predictable (CWE-330).
Note that this can be bypassed using XSS.

Identify especially dangerous operations. When the user performs a dangerous operation, send a separate confirmation request to ensure that the user intended to perform that operation.
Note that this can be bypassed using XSS.

Use the ESAPI Session Management control.
This control includes a component for CSRF.

Do not use the GET method for any request that triggers a state change.

Phase: Implementation
Check the HTTP Referer header to see if the request originated from an expected page. This could break legitimate functionality, because users or proxies may have disabled sending the Referer for privacy reasons.

### Reference


* [ https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html ](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
* [ https://cwe.mitre.org/data/definitions/352.html ](https://cwe.mitre.org/data/definitions/352.html)


#### CWE Id: [ 352 ](https://cwe.mitre.org/data/definitions/352.html)


#### WASC Id: 9

#### Source ID: 3

### [ CSP: script-src unsafe-inline ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks. Including (but not limited to) Cross Site Scripting (XSS), and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://host.docker.internal:3000/
  * Node Name: `http://host.docker.internal:3000/`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/minor-protection
  * Node Name: `http://host.docker.internal:3000/minor-protection`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/pricing
  * Node Name: `http://host.docker.internal:3000/pricing`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `script-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/register
  * Node Name: `http://host.docker.internal:3000/register`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `script-src includes unsafe-inline.`

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ CSP: style-src unsafe-inline ](https://www.zaproxy.org/docs/alerts/10055/)



##### Medium (High)

### Description

Content Security Policy (CSP) is an added layer of security that helps to detect and mitigate certain types of attacks. Including (but not limited to) Cross Site Scripting (XSS), and data injection attacks. These attacks are used for everything from data theft to site defacement or distribution of malware. CSP provides a set of standard HTTP headers that allow website owners to declare approved sources of content that browsers should be allowed to load on that page — covered types are JavaScript, CSS, HTML frames, fonts, images and embeddable objects such as Java applets, ActiveX, audio and video files.

* URL: http://host.docker.internal:3000
  * Node Name: `http://host.docker.internal:3000`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/app
  * Node Name: `http://host.docker.internal:3000/app`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/minor-protection
  * Node Name: `http://host.docker.internal:3000/minor-protection`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/pricing
  * Node Name: `http://host.docker.internal:3000/pricing`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `style-src includes unsafe-inline.`
* URL: http://host.docker.internal:3000/register
  * Node Name: `http://host.docker.internal:3000/register`
  * Method: `GET`
  * Parameter: `Content-Security-Policy`
  * Attack: ``
  * Evidence: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: http://127.0.0.1:8090 http://localhost:8090; media-src 'self' blob: http://127.0.0.1:8090 http://localhost:8090; font-src 'self' data:; connect-src 'self' http://127.0.0.1:8090 http://localhost:8090; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`
  * Other Info: `style-src includes unsafe-inline.`

Instances: Systemic


### Solution

Ensure that your web server, application server, load balancer, etc. is properly configured to set the Content-Security-Policy header.

### Reference


* [ https://www.w3.org/TR/CSP/ ](https://www.w3.org/TR/CSP/)
* [ https://caniuse.com/#search=content+security+policy ](https://caniuse.com/#search=content+security+policy)
* [ https://content-security-policy.com/ ](https://content-security-policy.com/)
* [ https://github.com/HtmlUnit/htmlunit-csp ](https://github.com/HtmlUnit/htmlunit-csp)
* [ https://web.dev/articles/csp#resource-options ](https://web.dev/articles/csp#resource-options)


#### CWE Id: [ 693 ](https://cwe.mitre.org/data/definitions/693.html)


#### WASC Id: 15

#### Source ID: 3

### [ Storable and Cacheable Content ](https://www.zaproxy.org/docs/alerts/10049/)



##### Informational (Medium)

### Description

The response contents are storable by caching components such as proxy servers, and may be retrieved directly from the cache, rather than from the origin server by the caching servers, in response to similar requests from other users. If the response data is sensitive, personal or user-specific, this may result in sensitive information being leaked. In some cases, this may even result in a user gaining complete control of the session of another user, depending on the configuration of the caching components in use in their environment. This is primarily an issue where "shared" caching servers such as "proxy" caches are configured on the local network. This configuration is typically found in corporate or educational environments, for instance.

* URL: http://host.docker.internal:3000/download
  * Node Name: `http://host.docker.internal:3000/download`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `s-maxage=31536000`
  * Other Info: ``
* URL: http://host.docker.internal:3000/help
  * Node Name: `http://host.docker.internal:3000/help`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `s-maxage=31536000`
  * Other Info: ``
* URL: http://host.docker.internal:3000/minor-protection
  * Node Name: `http://host.docker.internal:3000/minor-protection`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `s-maxage=31536000`
  * Other Info: ``
* URL: http://host.docker.internal:3000/pricing
  * Node Name: `http://host.docker.internal:3000/pricing`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `s-maxage=600`
  * Other Info: ``
* URL: http://host.docker.internal:3000/register
  * Node Name: `http://host.docker.internal:3000/register`
  * Method: `GET`
  * Parameter: ``
  * Attack: ``
  * Evidence: `s-maxage=31536000`
  * Other Info: ``

Instances: Systemic


### Solution

Validate that the response does not contain sensitive, personal or user-specific information. If it does, consider the use of the following HTTP response headers, to limit, or prevent the content being stored and retrieved from the cache by another user:
Cache-Control: no-cache, no-store, must-revalidate, private
Pragma: no-cache
Expires: 0
This configuration directs both HTTP 1.0 and HTTP 1.1 compliant caching servers to not store the response, and to not retrieve the response (without validation) from the cache, in response to a similar request.

### Reference


* [ https://datatracker.ietf.org/doc/html/rfc7234 ](https://datatracker.ietf.org/doc/html/rfc7234)
* [ https://datatracker.ietf.org/doc/html/rfc7231 ](https://datatracker.ietf.org/doc/html/rfc7231)
* [ https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html ](https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html)


#### CWE Id: [ 524 ](https://cwe.mitre.org/data/definitions/524.html)


#### WASC Id: 13

#### Source ID: 3


