// Mock for @/lib/api
const mockGet = jest.fn(() => Promise.resolve({ data: {} }));
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
const mockPut = jest.fn(() => Promise.resolve({ data: {} }));
const mockDelete = jest.fn(() => Promise.resolve({ data: {} }));

const api = {
  get: mockGet,
  post: mockPost,
  put: mockPut,
  delete: mockDelete,
  interceptors: {
    response: { use: jest.fn() },
    request: { use: jest.fn() },
  },
  defaults: { baseURL: "http://test/api" },
};

const API = "http://test/api";
const BACKEND_URL = "http://test";

function markRecentAuth() {}

module.exports = { api, API, BACKEND_URL, markRecentAuth };
