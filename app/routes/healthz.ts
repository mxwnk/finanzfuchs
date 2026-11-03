/** For the container's health check; needs no login and touches no data. */
export function loader() {
  return new Response("ok", { headers: { "Content-Type": "text/plain" } });
}
