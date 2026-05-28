# Документация по superAppTkn

SuperApp token
This token is required for confirming authentication or obtaining permissions to perform certain actions without passing an Access token.
This article is about SuperApp token version 2.0.
Obtaining SuperApp token
To generate a SuperApp token, execute the following script from the example.
Script example
const currentTime = Date.now() / 1000;
const tokenBody = {
"access_token": "\*_\*\*",
"iat": currentTime,
"exp": currentTime + (60 _ 60),
"subject": "superappkit-web",
"payload": {},
}

const serviceKey = "..."; // App service token (can be obtained in app settings).

const superAppToken = encrypt(JSON.stringify(tokenBody), serviceKey); // See below for an example implementation of the encrypt method.

return superAppToken;
Description of script parameters
Parameter Type Description
access_token String Token obtained via exchange of Silent Token for Access token
iat Int Timestamp of the creation date of the SuperApp token in seconds
exp Int Timestamp of the expiration date of the token in seconds. Should be no more than iat + one hour
subject String Action for confirmation of which the SuperApp token is generated. Possible value: "subject": "superappkit-web". Currently used to sign a user out of your service
payload object Additional parameters that may be needed for the current action (the subject parameter)
Example implementation of SuperApp token in Node.js
'use strict';

const crypto = require('crypto');

const IV_LENGTH = 16; // For AES, this is always 16

function encrypt(text, key) {
const [encryptKey, signKey] = prepareKeys(key);

let iv = crypto.randomBytes(IV_LENGTH);
let cipher = crypto.createCipheriv('aes-256-cbc', encryptKey, iv);
let encrypted = cipher.update(text);

encrypted = Buffer.concat([encrypted, cipher.final()]);
encrypted = Buffer.concat([iv, encrypted]);
let signature = hmac(encrypted, signKey);

# Документация по Access tkn

Access token
Access token is the signature of the user in your application. The token is issued after the user has logged into the service using the VK ID. It tells the server on behalf of which user requests are made in the API and what access rights the user has granted to your application.
Access token has a limited lifespan of 1 hour.
How to get a token
To obtain an Access token, use the confirmation code. Such code can only be obtained from the frontend of the application - user confirmation is required that he allows the application to access the API on his own behalf.
There are two ways to get an Access token by Authorization Code Flow:
(recommended) when the exchange of the authorization code for the token occurs from the backend of the application. This is a safer way, since the received token will not be stored in clear text, but on the backend - it is more difficult for the malicious to get to the token;
when the authorization code is exchanged for a token from the application frontend. This method is possible if your application does not have a backend.
Be sure to use the PKCE extension to protect the transmitted data.
Pay attention
The ability to exchange confirmation code for tokens depends on the architecture of your application and what parameters the service passed to the SDK to support PKCE.
If your web application is divided into frontend and backend and you use SDK authorization scheme with code exchange on backend, your service sends a codeChallenge to the SDK - the exchange of confirmation code for tokens is possible only through a call to id.vk.com/oauth2/auth, where grant*type = authorization_code. Learn more
If there is no such separation, only the frontend is used and you use SDK authorization scheme with code exchange on the frontend, options are possible:
your service passed codeVerifier to the SDK - the confirmation code can be exchanged for tokens using the SDK VKID.Auth.exchangeCode (code, device_id) method or through a call to id.vk.com/oauth2/auth, where grant_type = authorization_code. Learn more;
your service did not pass codeVerifier to the SDK - exchange is possible only through the SDK method VKID.Auth.exchangeCode (code, device_id).
Sample Response
{
"access_token": "\***\*",
"refresh_token": "\*\***",
"token_type": "Bearer",
"expires_in": 3600,
"user_id": 1234567890,
"id_token": "\*\*\*\*",
"scope": "email phone"
}
Description of response parameters
Name Description
access_token Access token
refresh_token Refresh token, that is intended to update an Access token that is about to expire
token_type Type of token issued. Always takes value bearer
expires_in Time in seconds after which Access token expires
user_id User ID
id_token ID token to obtain user data. Always takes value id_token
Disability Access token
In the SDK for Web, you can disable a token and log out of a user account using the SDK logout() method.
Usage example
VKID.Auth.logout(access_token);
As a result of the method, both Access token and Refresh token become invalid.
How to use a token to find out if a user's account is confirmed
A gray check mark next to the user name means that he indicated genuine personal data in the account and confirmed it.
You can also get this information using the [users.get ()] (https://dev.vk.com/ru/method/users.get) method. It returns is_verified = true if the user's account is confirmed, or is * verified = false if the data is not confirmed.

# пример входящих данных

ref = {
"refresh_token": "",
"access_token": "",
"id_token": "",
"token_type": "Bearer",
"expires_in": 3600,
"user_id": 192567609,
"state": "b-0O-R8bJqOWGFwOm-3mKRyZMb5XK6C8eeUFyoJSCgnRZbPV",
"scope": "vkid.personal_info",
}

# Запрос пользователя

https://api.vk.com/method/users.get?fields=screen_name&access_token={accesstkn}&v=5.199

# ответ на запрос

{
"response": [
{
"id": 192567609,
"screen_name": "meowthpxnk",
"first_name": "Владислав",
"last_name": "Хромых",
"can_access_closed": true,
"is_closed": false
}
]
}

# про username

если приходит screen*name то мы устанавливаем screen_name
если занято то подставляем к screen name + "*{rand}" рандомный набор из четырех цифр если такой уже попался то генерим еще раз до пяти и отправляем ошибку
если вдруг screen-name нету то делаем связку "{first*name}*{last*name}" транслитом, а если занято то "*{rand}" так же как и со screen_name

# задача

необходимо сделать доп таблицу vk-id-mapping
Предварительно сделав запрос на пользователя, чтобы могли доверять accesstkn vk
и если приходит входящие данные с существующим vk-id то входит в этот аккаунт и авторизует потипу BearerTkn
если приходит id которого нет в таблице маппинга создает аккаунт пользователя с Фио которое пришло в ответе и так же авторизует по типу моей авторизации Bearer
