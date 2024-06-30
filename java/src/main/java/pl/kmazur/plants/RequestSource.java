package pl.kmazur.plants;

import java.util.List;

public interface RequestSource {
    List<Request> getRequests();
    void markRequestFulfilled(Request request);
    void markRequestFulfilled(String requestName);
}

